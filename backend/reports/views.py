# apps/reports/views.py
# ---------------------------------------------------------------------------
# No models in this app — pure read-only query layer.
# All views require authentication. Staff views additionally require
# VIEW_ALL_REPORTS permission checked at the view level.
# ---------------------------------------------------------------------------

from decimal import Decimal
from django.db.models import Sum, Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from accounts.models import User, UserStatus
from permissions.models import PermissionCode
from submissions.models import CapitalSubmissionRequest, RequestStatus
from ledger.models import MemberCapitalLedgerEntry, EntryType
from investments.models import Investment, InvestmentStatus
from snapshots.models import InvestmentSnapshotHeader
from distributions.models import InvestmentDistribution, DistributionStatus, InvestmentDistributionLine


from .csv_utils import streaming_csv_response


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _has_perm(request, code):
    return request.user.has_permission(code)


def _forbidden():
    return Response(
        {"detail": "You do not have permission to perform this action.", "errors": None},
        status=status.HTTP_403_FORBIDDEN,
    )


def _compute_running_balance(entries):
    """
    Attach a cumulative running_balance to each ledger entry dict.
    Entries must already be ordered by txn_date ASC, created_at ASC.
    """
    running = Decimal("0")
    result  = []
    for e in entries:
        running += e["amount"]
        result.append({**e, "running_balance": running})
    return result


# ---------------------------------------------------------------------------
# Member: personal statement (FR-10)
# ---------------------------------------------------------------------------

class MyStatementView(APIView):
    """
    GET /api/reports/my-statement/

    Returns the authenticated member's full ledger statement including:
      - current_balance (authorized entries only — BR-06)
      - pending_total   (informational — not in balance)
      - entries with running balance computed per row
      - pending submission requests listed separately

    Query params:
      ?from_date=YYYY-MM-DD
      ?to_date=YYYY-MM-DD
      ?entry_type=SUBMISSION|WITHDRAW|ADJUSTMENT|DISTRIBUTION|DISTRIBUTION_REVERSAL
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        qs = (
            MemberCapitalLedgerEntry.objects
            .filter(user=user)
            .select_related("created_by")
            .order_by("txn_date", "created_at")
        )

        # Apply filters
        from_date  = request.query_params.get("from_date")
        to_date    = request.query_params.get("to_date")
        entry_type = request.query_params.get("entry_type")

        if from_date:
            qs = qs.filter(txn_date__gte=from_date)
        if to_date:
            qs = qs.filter(txn_date__lte=to_date)
        if entry_type:
            qs = qs.filter(entry_type=entry_type.upper())

        # Build entry dicts with running balance
        raw_entries = list(qs.values(
            "ledger_id", "entry_type", "amount", "currency",
            "txn_date", "reference_type", "reference_id",
            "comment", "created_at", "created_by__full_name",
        ))
        entries_with_balance = _compute_running_balance(raw_entries)

        # Current balance from ALL entries (ignoring date filter for total)
        current_balance = (
            MemberCapitalLedgerEntry.objects
            .filter(user=user)
            .aggregate(total=Sum("amount"))["total"]
            or Decimal("0")
        )

        # Pending requests — shown separately (BR-06)
        pending_qs = (
            CapitalSubmissionRequest.objects
            .filter(user=user, status=RequestStatus.PENDING)
            .values(
                "request_id", "request_type", "amount",
                "txn_date", "payment_channel", "external_reference",
                "notes", "requested_at",
            )
            .order_by("requested_at")
        )
        pending_total = (
            pending_qs.aggregate(total=Sum("amount"))["total"]
            or Decimal("0")
        )

        return Response(
            {
                "member": {
                    "user_id":    str(user.user_id),
                    "full_name":  user.full_name,
                    "contact_no": user.contact_no,
                    "join_date":  user.join_date,
                },
                "current_balance": current_balance,
                "pending_total":   pending_total,
                "entry_count":     len(entries_with_balance),
                "entries":         entries_with_balance,
                "pending_requests": list(pending_qs),
            },
            status=status.HTTP_200_OK,
        )


# ---------------------------------------------------------------------------
# Member: personal distribution history
# ---------------------------------------------------------------------------

class MyDistributionsView(APIView):
    """
    GET /api/reports/my-distributions/

    Returns all investments where the authenticated member received
    a P/L distribution share, with the investment title and share amount.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        

        lines = (
            InvestmentDistributionLine.objects
            .filter(user=request.user)
            .select_related(
                "distribution__investment",
                "distribution__posted_by",
                "ledger_entry",
            )
            .order_by("-distribution__posted_at")
        )

        data = [
            {
                "distribution_id":   str(line.distribution.distribution_id),
                "investment_id":     str(line.distribution.investment.investment_id),
                "investment_title":  line.distribution.investment.title,
                "investment_type":   line.distribution.investment.investment_type,
                "pnl_amount":        line.distribution.pnl_amount,
                "distribution_status": line.distribution.status,
                "ratio_used":        line.ratio_used,
                "share_amount":      line.share_amount,
                "posted_at":         line.distribution.posted_at,
                "posted_by":         line.distribution.posted_by.full_name,
                "ledger_entry_id":   str(line.ledger_entry.ledger_id),
            }
            for line in lines
        ]

        total_received = sum(
            d["share_amount"] for d in data
            if d["distribution_status"] == DistributionStatus.POSTED
        )

        return Response(
            {
                "total_received":    total_received,
                "distribution_count": len(data),
                "distributions":     data,
            },
            status=status.HTTP_200_OK,
        )


# ---------------------------------------------------------------------------
# Staff: association summary (FR-10)
# ---------------------------------------------------------------------------

class AssociationSummaryView(APIView):
    """
    GET /api/reports/association-summary/
    Requires VIEW_ALL_REPORTS.

    High-level financial snapshot of the entire association:
      - total authorized capital
      - total pending (not yet approved)
      - member counts by status
      - investment counts by status
      - total PnL distributed across all investments
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_perm(request, PermissionCode.VIEW_ALL_REPORTS):
            return _forbidden()

        # Capital
        total_capital = (
            MemberCapitalLedgerEntry.objects
            .aggregate(total=Sum("amount"))["total"]
            or Decimal("0")
        )
        total_pending = (
            CapitalSubmissionRequest.objects
            .filter(status=RequestStatus.PENDING)
            .aggregate(total=Sum("amount"))["total"]
            or Decimal("0")
        )

        # Members
        member_counts = User.objects.aggregate(
            total=Count("user_id"),
            active=Count("user_id", filter=Q(status=UserStatus.ACTIVE)),
            inactive=Count("user_id", filter=Q(status=UserStatus.INACTIVE)),
        )

        # Investments
        inv_counts = Investment.objects.aggregate(
            total=Count("investment_id"),
            draft=Count("investment_id", filter=Q(status=InvestmentStatus.DRAFT)),
            open=Count("investment_id", filter=Q(status=InvestmentStatus.OPEN)),
            closed=Count("investment_id", filter=Q(status=InvestmentStatus.CLOSED)),
            distributed=Count("investment_id", filter=Q(status=InvestmentStatus.DISTRIBUTED)),
            reversed=Count("investment_id", filter=Q(status=InvestmentStatus.REVERSED)),
        )
        total_invested = (
            Investment.objects
            .exclude(status=InvestmentStatus.DRAFT)
            .aggregate(total=Sum("invested_amount"))["total"]
            or Decimal("0")
        )

        # Distributions
        total_distributed_pnl = (
            InvestmentDistribution.objects
            .filter(status=DistributionStatus.POSTED)
            .aggregate(total=Sum("pnl_amount"))["total"]
            or Decimal("0")
        )

        # Submissions
        submission_counts = CapitalSubmissionRequest.objects.aggregate(
            total=Count("request_id"),
            pending=Count("request_id", filter=Q(status=RequestStatus.PENDING)),
            approved=Count("request_id", filter=Q(status=RequestStatus.APPROVED)),
            rejected=Count("request_id", filter=Q(status=RequestStatus.REJECTED)),
        )

        return Response(
            {
                "generated_at": timezone.now(),
                "capital": {
                    "total_authorized": total_capital,
                    "total_pending":    total_pending,
                    "total_invested":   total_invested,
                },
                "members": member_counts,
                "investments": inv_counts,
                "distributions": {
                    "total_pnl_distributed": total_distributed_pnl,
                },
                "submissions": submission_counts,
            },
            status=status.HTTP_200_OK,
        )


# ---------------------------------------------------------------------------
# Staff: all member balances
# ---------------------------------------------------------------------------

class MemberBalancesView(APIView):
    """
    GET /api/reports/member-balances/
    Requires VIEW_ALL_REPORTS.

    Returns every member with their current authorized balance.
    Ordered by balance descending by default.

    Query params: ?status=ACTIVE|INACTIVE  ?search=<name>
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_perm(request, PermissionCode.VIEW_ALL_REPORTS):
            return _forbidden()

        users_qs = User.objects.all()

        status_filter = request.query_params.get("status")
        search        = request.query_params.get("search")

        if status_filter:
            users_qs = users_qs.filter(status=status_filter.upper())
        if search:
            users_qs = users_qs.filter(full_name__icontains=search)

        # Compute balance per user via a subquery annotation
        from django.db.models import OuterRef, Subquery
        balance_subquery = (
            MemberCapitalLedgerEntry.objects
            .filter(user=OuterRef("pk"))
            .values("user")
            .annotate(total=Sum("amount"))
            .values("total")
        )

        users_with_balance = (
            users_qs
            .annotate(balance=Subquery(balance_subquery))
            .order_by("-balance", "full_name")
        )

        data = [
            {
                "user_id":    str(u.user_id),
                "full_name":  u.full_name,
                "contact_no": u.contact_no,
                "email":      u.email,
                "join_date":  u.join_date,
                "role":       u.role,
                "status":     u.status,
                "balance":    u.balance or Decimal("0"),
            }
            for u in users_with_balance
        ]

        total_capital = sum(d["balance"] for d in data)

        return Response(
            {
                "total_capital": total_capital,
                "member_count":  len(data),
                "members":       data,
            },
            status=status.HTTP_200_OK,
        )


# ---------------------------------------------------------------------------
# Staff: investment register
# ---------------------------------------------------------------------------

class InvestmentRegisterView(APIView):
    """
    GET /api/reports/investment-register/
    Requires VIEW_ALL_REPORTS.

    Full register of all investments with financial summary.
    Query params: ?status=DRAFT|OPEN|CLOSED|DISTRIBUTED|REVERSED
                  ?investment_type=FIXED_DEPOSIT|EQUITY|...
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_perm(request, PermissionCode.VIEW_ALL_REPORTS):
            return _forbidden()

        qs = (
            Investment.objects
            .select_related("created_by", "fund_released_by")
            .order_by("-created_date")
        )

        status_filter = request.query_params.get("status")
        type_filter   = request.query_params.get("investment_type")

        if status_filter:
            qs = qs.filter(status=status_filter.upper())
        if type_filter:
            qs = qs.filter(investment_type=type_filter.upper())

        data = []
        for inv in qs:
            member_count = 0
            try:
                member_count = inv.snapshot.member_count
            except Exception:
                pass

            pnl = None
            if inv.return_amount is not None:
                pnl = inv.return_amount - inv.invested_amount

            data.append({
                "investment_id":    str(inv.investment_id),
                "title":            inv.title,
                "investment_type":  inv.investment_type,
                "invested_to":      inv.invested_to,
                "invested_amount":  inv.invested_amount,
                "return_amount":    inv.return_amount,
                "pnl_amount":       pnl,
                "created_date":     inv.created_date,
                "close_date":       inv.close_date,
                "status":           inv.status,
                "member_count":     member_count,
                "created_by":       inv.created_by.full_name,
                "fund_released_by": inv.fund_released_by.full_name if inv.fund_released_by else None,
                "fund_released_at": inv.fund_released_at,
            })

        return Response(
            {
                "investment_count": len(data),
                "investments":      data,
            },
            status=status.HTTP_200_OK,
        )


# ---------------------------------------------------------------------------
# Staff: distribution logs
# ---------------------------------------------------------------------------

class DistributionLogsView(APIView):
    """
    GET /api/reports/distribution-logs/
    Requires VIEW_ALL_REPORTS.

    All distributions across all investments (both POSTED and REVERSED).
    Query params: ?status=POSTED|REVERSED  ?investment_id=<uuid>
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_perm(request, PermissionCode.VIEW_ALL_REPORTS):
            return _forbidden()

        qs = (
            InvestmentDistribution.objects
            .select_related("investment", "posted_by", "reversed_by")
            .order_by("-posted_at")
        )

        status_filter     = request.query_params.get("status")
        investment_filter = request.query_params.get("investment_id")

        if status_filter:
            qs = qs.filter(status=status_filter.upper())
        if investment_filter:
            qs = qs.filter(investment__investment_id=investment_filter)

        data = [
            {
                "distribution_id":   str(d.distribution_id),
                "investment_id":     str(d.investment.investment_id),
                "investment_title":  d.investment.title,
                "pnl_amount":        d.pnl_amount,
                "rounded_total":     d.rounded_total,
                "remainder_applied": d.remainder_applied,
                "status":            d.status,
                "posted_by":         d.posted_by.full_name,
                "posted_at":         d.posted_at,
                "reversed_by":       d.reversed_by.full_name if d.reversed_by else None,
                "reversed_at":       d.reversed_at,
                "member_count":      d.lines.count(),
            }
            for d in qs
        ]

        return Response(
            {
                "distribution_count": len(data),
                "distributions":      data,
            },
            status=status.HTTP_200_OK,
        )


# ---------------------------------------------------------------------------
# Staff: approval queue report
# ---------------------------------------------------------------------------

class ApprovalQueueReportView(APIView):
    """
    GET /api/reports/approval-queue-report/
    Requires VIEW_ALL_REPORTS.

    Summary of all PENDING submission requests, grouped by payment channel.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_perm(request, PermissionCode.VIEW_ALL_REPORTS):
            return _forbidden()

        pending_qs = (
            CapitalSubmissionRequest.objects
            .filter(status=RequestStatus.PENDING)
            .select_related("user")
            .prefetch_related("attachments")
            .order_by("requested_at")
        )

        by_channel = {}
        items      = []

        for req in pending_qs:
            channel = req.payment_channel
            by_channel.setdefault(channel, {"count": 0, "total_amount": Decimal("0")})
            by_channel[channel]["count"]        += 1
            by_channel[channel]["total_amount"] += req.amount

            items.append({
                "request_id":        str(req.request_id),
                "member_name":       req.user.full_name,
                "member_contact":    req.user.contact_no,
                "request_type":      req.request_type,
                "amount":            req.amount,
                "txn_date":          req.txn_date,
                "payment_channel":   req.payment_channel,
                "external_reference": req.external_reference,
                "notes":             req.notes,
                "requested_at":      req.requested_at,
                "attachment_count":  req.attachments.count(),
            })

        total_pending = sum(i["amount"] for i in items)

        return Response(
            {
                "total_pending_amount": total_pending,
                "total_pending_count":  len(items),
                "by_channel":           by_channel,
                "items":                items,
            },
            status=status.HTTP_200_OK,
        )


# ===========================================================================
# CSV EXPORTS
# ===========================================================================

class ExportMemberBalancesCSV(APIView):
    """GET /api/reports/export/member-balances/"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_perm(request, PermissionCode.VIEW_ALL_REPORTS):
            return _forbidden()

        from django.db.models import OuterRef, Subquery

        balance_subquery = (
            MemberCapitalLedgerEntry.objects
            .filter(user=OuterRef("pk"))
            .values("user")
            .annotate(total=Sum("amount"))
            .values("total")
        )

        users = (
            User.objects
            .annotate(balance=Subquery(balance_subquery))
            .order_by("-balance", "full_name")
        )

        def rows():
            yield ["user_id", "full_name", "contact_no", "email",
                   "join_date", "role", "status", "balance_bdt"]
            for u in users.iterator():
                yield [
                    str(u.user_id), u.full_name, u.contact_no,
                    u.email or "", u.join_date, u.role, u.status,
                    u.balance or "0.00",
                ]

        return streaming_csv_response(rows(), "member_balances.csv")


class ExportInvestmentRegisterCSV(APIView):
    """GET /api/reports/export/investment-register/"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_perm(request, PermissionCode.VIEW_ALL_REPORTS):
            return _forbidden()

        qs = (
            Investment.objects
            .select_related("created_by", "fund_released_by")
            .order_by("-created_date")
        )

        def rows():
            yield [
                "investment_id", "title", "investment_type", "invested_to",
                "invested_amount", "return_amount", "pnl_amount",
                "created_date", "close_date", "status",
                "member_count", "created_by", "fund_released_by",
            ]
            for inv in qs.iterator():
                member_count = 0
                try:
                    member_count = inv.snapshot.member_count
                except Exception:
                    pass

                pnl = (
                    inv.return_amount - inv.invested_amount
                    if inv.return_amount is not None else ""
                )
                yield [
                    str(inv.investment_id), inv.title,
                    inv.investment_type, inv.invested_to,
                    inv.invested_amount, inv.return_amount or "",
                    pnl, inv.created_date, inv.close_date or "",
                    inv.status, member_count,
                    inv.created_by.full_name,
                    inv.fund_released_by.full_name if inv.fund_released_by else "",
                ]

        return streaming_csv_response(rows(), "investment_register.csv")


class ExportDistributionLogsCSV(APIView):
    """GET /api/reports/export/distribution-logs/"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_perm(request, PermissionCode.VIEW_ALL_REPORTS):
            return _forbidden()

        qs = (
            InvestmentDistribution.objects
            .select_related("investment", "posted_by", "reversed_by")
            .order_by("-posted_at")
        )

        def rows():
            yield [
                "distribution_id", "investment_title",
                "pnl_amount", "rounded_total", "remainder_applied",
                "status", "posted_by", "posted_at",
                "reversed_by", "reversed_at",
            ]
            for d in qs.iterator():
                yield [
                    str(d.distribution_id), d.investment.title,
                    d.pnl_amount, d.rounded_total, d.remainder_applied,
                    d.status, d.posted_by.full_name, d.posted_at,
                    d.reversed_by.full_name if d.reversed_by else "",
                    d.reversed_at or "",
                ]

        return streaming_csv_response(rows(), "distribution_logs.csv")


class ExportMemberStatementCSV(APIView):
    """GET /api/reports/export/member-statement/{user_id}/"""
    permission_classes = [IsAuthenticated]

    def get(self, request, user_id):
        # Members can export their own. Staff can export anyone's.
        is_own   = str(request.user.user_id) == str(user_id)
        is_staff = _has_perm(request, PermissionCode.VIEW_ALL_REPORTS)

        if not (is_own or is_staff):
            return _forbidden()

        user = get_object_or_404(User, user_id=user_id)
        qs   = (
            MemberCapitalLedgerEntry.objects
            .filter(user=user)
            .order_by("txn_date", "created_at")
        )

        def rows():
            yield [
                "ledger_id", "entry_type", "amount", "currency",
                "txn_date", "running_balance",
                "reference_type", "reference_id", "comment", "created_at",
            ]
            running = Decimal("0")
            for e in qs.iterator():
                running += e.amount
                yield [
                    str(e.ledger_id), e.entry_type, e.amount,
                    e.currency, e.txn_date, running,
                    e.reference_type, e.reference_id,
                    e.comment, e.created_at,
                ]

        filename = f"statement_{user.contact_no}.csv"
        return streaming_csv_response(rows(), filename)