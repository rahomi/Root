# apps/ledger/views.py

from decimal import Decimal
from django.db import models
from django.db.models import Sum
from django.shortcuts import get_object_or_404

from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from accounts.models import User
from permissions.models import PermissionCode
from audit.utils import log_action
from submissions.models import CapitalSubmissionRequest, RequestStatus

from .models import (
    MemberCapitalLedgerEntry,
    EntryType,
    ReferenceType,
)
from .serializers import (
    LedgerEntrySerializer,
    AdminLedgerEntrySerializer,
    AdminLedgerPostSerializer,
)


def _has_perm(request, code):
    return request.user.has_permission(code)


def _forbidden():
    return Response(
        {"detail": "You do not have permission to perform this action.", "errors": None},
        status=status.HTTP_403_FORBIDDEN,
    )


def _compute_balance(user):
    result = (
        MemberCapitalLedgerEntry.objects
        .filter(user=user)
        .aggregate(total=Sum("amount"))
    )
    return result["total"] or Decimal("0")


def _compute_pending_total(user):
    """Sum of amounts on PENDING submission requests — not yet in the ledger."""
    result = (
        CapitalSubmissionRequest.objects
        .filter(user=user, status=RequestStatus.PENDING)
        .aggregate(total=Sum("amount"))
    )
    return result["total"] or Decimal("0")


def _apply_ledger_filters(qs, query_params):
    entry_type = query_params.get("entry_type")
    from_date = query_params.get("from_date")
    to_date = query_params.get("to_date")

    if entry_type:
        entry_type = entry_type.upper()
        if entry_type not in EntryType.values:
            return None, Response(
                {
                    "detail": (
                        "entry_type must be one of: "
                        f"{', '.join(EntryType.values)}."
                    ),
                    "errors": {"entry_type": ["Invalid entry_type filter."]},
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        qs = qs.filter(entry_type=entry_type)
    if from_date:
        qs = qs.filter(txn_date__gte=from_date)
    if to_date:
        qs = qs.filter(txn_date__lte=to_date)

    return qs, None


# ---------------------------------------------------------------------------
# Member: own ledger statement
# ---------------------------------------------------------------------------

class MemberLedgerView(APIView):
    """
    GET /api/ledger/
    Returns the authenticated member's:
      - current_balance  (sum of posted ledger entries only — BR-06)
      - pending_total    (sum of PENDING submission requests — informational only)
      - paginated ledger entries ordered by txn_date ascending

    Query params:
      ?entry_type=SUBMISSION|WITHDRAW|ADJUSTMENT|DISTRIBUTION|DISTRIBUTION_REVERSAL
      ?from_date=YYYY-MM-DD
      ?to_date=YYYY-MM-DD
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        qs   = (
            MemberCapitalLedgerEntry.objects
            .filter(user=user)
            .select_related("created_by")
            .order_by("txn_date", "created_at")
        )

        qs, err = _apply_ledger_filters(qs, request.query_params)
        if err:
            return err

        entries         = list(qs)
        current_balance = _compute_balance(user)
        pending_total   = _compute_pending_total(user)

        return Response(
            {
                "current_balance": current_balance,
                "pending_total":   pending_total,
                "entry_count":     len(entries),
                "entries":         LedgerEntrySerializer(entries, many=True).data,
            },
            status=status.HTTP_200_OK,
        )


# ---------------------------------------------------------------------------
# Admin: view any member's ledger
# ---------------------------------------------------------------------------

class AdminMemberLedgerView(APIView):
    """
    GET /api/ledger/members/{user_id}/
    Staff with VIEW_ALL_REPORTS can view any member's full ledger.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, user_id):
        if not _has_perm(request, PermissionCode.VIEW_ALL_REPORTS):
            return _forbidden()

        user = get_object_or_404(User, user_id=user_id)

        qs = (
            MemberCapitalLedgerEntry.objects
            .filter(user=user)
            .select_related("created_by")
            .order_by("txn_date", "created_at")
        )

        qs, err = _apply_ledger_filters(qs, request.query_params)
        if err:
            return err

        entries         = list(qs)
        current_balance = _compute_balance(user)
        pending_total   = _compute_pending_total(user)

        return Response(
            {
                "user": {
                    "user_id":    str(user.user_id),
                    "full_name":  user.full_name,
                    "contact_no": user.contact_no,
                },
                "current_balance": current_balance,
                "pending_total":   pending_total,
                "entry_count":     len(entries),
                "entries":         LedgerEntrySerializer(entries, many=True).data,
            },
            status=status.HTTP_200_OK,
        )


# ---------------------------------------------------------------------------
# Admin: all ledger entries
# ---------------------------------------------------------------------------

class AdminLedgerView(APIView):
    """
    GET /api/ledger/admin/
    Staff with VIEW_ALL_REPORTS can view all member ledger entries.

    Query params:
      ?entry_type=SUBMISSION|WITHDRAW|ADJUSTMENT|DISTRIBUTION|DISTRIBUTION_REVERSAL
      ?from_date=YYYY-MM-DD
      ?to_date=YYYY-MM-DD
      ?user_id=<uuid>
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_perm(request, PermissionCode.VIEW_ALL_REPORTS):
            return _forbidden()

        qs = (
            MemberCapitalLedgerEntry.objects
            .select_related("user", "created_by")
            .order_by("-txn_date", "-created_at")
        )

        user_id = request.query_params.get("user_id")
        if user_id:
            qs = qs.filter(user__user_id=user_id)

        qs, err = _apply_ledger_filters(qs, request.query_params)
        if err:
            return err

        totals = qs.aggregate(
            total_in=Sum("amount", filter=models.Q(amount__gt=0)),
            total_out=Sum("amount", filter=models.Q(amount__lt=0)),
        )
        entries = list(qs)

        return Response(
            {
                "total_in": totals["total_in"] or Decimal("0"),
                "total_out": abs(totals["total_out"] or Decimal("0")),
                "entry_count": len(entries),
                "entries": AdminLedgerEntrySerializer(entries, many=True).data,
            },
            status=status.HTTP_200_OK,
        )


# ---------------------------------------------------------------------------
# Admin: direct ledger post (FR-05)
# ---------------------------------------------------------------------------

class AdminLedgerPostView(APIView):
    """
    POST /api/ledger/admin-post/
    Requires POST_ADMIN_LEDGER permission.
    Allowed types: SUBMISSION, WITHDRAW, ADJUSTMENT.
    Each entry is immutable once created.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not _has_perm(request, PermissionCode.POST_ADMIN_LEDGER):
            return _forbidden()

        serializer = AdminLedgerPostSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data       = serializer.validated_data
        target_user = serializer._target_user

        entry = MemberCapitalLedgerEntry.objects.create(
            user=target_user,
            entry_type=data["entry_type"],
            amount=data["amount"],
            txn_date=data["txn_date"],
            reference_type=ReferenceType.MANUAL,
            reference_id=data.get("reference_id", ""),
            comment=data["comment"],
            created_by=request.user,
        )

        log_action(
            "MemberCapitalLedgerEntry",
            entry.ledger_id,
            "CREATE",
            request.user,
            after={
                "target_user":  str(target_user.user_id),
                "entry_type":   entry.entry_type,
                "amount":       str(entry.amount),
            },
        )

        new_balance = _compute_balance(target_user)

        return Response(
            {
                "entry":       LedgerEntrySerializer(entry).data,
                "new_balance": new_balance,
            },
            status=status.HTTP_201_CREATED,
        )
