# apps/ledger/views.py

from decimal import Decimal
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

        # Filters
        entry_type = request.query_params.get("entry_type")
        from_date  = request.query_params.get("from_date")
        to_date    = request.query_params.get("to_date")

        if entry_type:
            qs = qs.filter(entry_type=entry_type.upper())
        if from_date:
            qs = qs.filter(txn_date__gte=from_date)
        if to_date:
            qs = qs.filter(txn_date__lte=to_date)

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

        entry_type = request.query_params.get("entry_type")
        from_date  = request.query_params.get("from_date")
        to_date    = request.query_params.get("to_date")

        if entry_type:
            qs = qs.filter(entry_type=entry_type.upper())
        if from_date:
            qs = qs.filter(txn_date__gte=from_date)
        if to_date:
            qs = qs.filter(txn_date__lte=to_date)

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