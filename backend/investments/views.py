# apps/investments/views.py

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from permissions.models import PermissionCode
from audit.utils import log_action
from snapshots.models import InvestmentSnapshotHeader

from .models import Investment, InvestmentStatus
from .serializers import (
    InvestmentCreateSerializer,
    InvestmentUpdateSerializer,
    InvestmentDetailSerializer,
    InvestmentListSerializer,
    ReleaseFundsSerializer,
    CloseInvestmentSerializer,
    SnapshotDetailSerializer,
)


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


def _bad_request(msg):
    return Response({"detail": msg, "errors": None}, status=status.HTTP_400_BAD_REQUEST)


# ---------------------------------------------------------------------------
# List + Create
# ---------------------------------------------------------------------------

class InvestmentListCreateView(APIView):
    """
    GET  /api/investments/   List investments (all authenticated users)
    POST /api/investments/   Create a DRAFT investment (CREATE_INVESTMENT)
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = (
            Investment.objects
            .select_related("created_by")
            .order_by("-created_date", "-created_at")
        )

        # Optional filters
        status_filter = request.query_params.get("status")
        type_filter   = request.query_params.get("investment_type")

        if status_filter:
            qs = qs.filter(status=status_filter.upper())
        if type_filter:
            qs = qs.filter(investment_type=type_filter.upper())

        serializer = InvestmentListSerializer(qs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        if not _has_perm(request, PermissionCode.CREATE_INVESTMENT):
            return _forbidden()

        serializer = InvestmentCreateSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        investment = serializer.save()

        log_action(
            "Investment", investment.investment_id, "CREATE", request.user,
            after={
                "title":           investment.title,
                "invested_amount": str(investment.invested_amount),
                "status":          investment.status,
            },
        )
        return Response(
            InvestmentDetailSerializer(investment).data,
            status=status.HTTP_201_CREATED,
        )


# ---------------------------------------------------------------------------
# Detail + Update
# ---------------------------------------------------------------------------

class InvestmentDetailView(APIView):
    """
    GET   /api/investments/{id}/   Anyone authenticated
    PATCH /api/investments/{id}/   DRAFT only (CREATE_INVESTMENT)
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, investment_id):
        investment = get_object_or_404(
            Investment.objects.select_related(
                "created_by", "fund_released_by"
            ),
            investment_id=investment_id,
        )
        return Response(
            InvestmentDetailSerializer(investment).data,
            status=status.HTTP_200_OK,
        )

    def patch(self, request, investment_id):
        if not _has_perm(request, PermissionCode.CREATE_INVESTMENT):
            return _forbidden()

        investment = get_object_or_404(Investment, investment_id=investment_id)

        if investment.status != InvestmentStatus.DRAFT:
            return _bad_request(
                f"Only DRAFT investments can be edited. "
                f"Current status: {investment.status}."
            )

        serializer = InvestmentUpdateSerializer(
            investment, data=request.data,
            partial=True, context={"request": request},
        )
        serializer.is_valid(raise_exception=True)

        before = InvestmentDetailSerializer(investment).data
        updated = serializer.save()
        after  = InvestmentDetailSerializer(updated).data

        log_action(
            "Investment", investment.investment_id, "UPDATE", request.user,
            before=dict(before), after=dict(after),
        )
        return Response(
            InvestmentDetailSerializer(updated).data,
            status=status.HTTP_200_OK,
        )


# ---------------------------------------------------------------------------
# Release funds: DRAFT → OPEN + snapshot capture
# ---------------------------------------------------------------------------

class ReleaseFundsView(APIView):
    """
    POST /api/investments/{id}/release-funds/

    FR-06 + BR-08:
      - Requires RELEASE_INVESTMENT_FUNDS permission.
      - Enforces segregation of duties: actor ≠ creator.
      - Transitions DRAFT → OPEN.
      - Atomically captures the member capital snapshot.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, investment_id):
        if not _has_perm(request, PermissionCode.RELEASE_INVESTMENT_FUNDS):
            return _forbidden()

        investment = get_object_or_404(Investment, investment_id=investment_id)

        # Validate state before calling service
        if investment.status != InvestmentStatus.DRAFT:
            return _bad_request(
                f"Only DRAFT investments can have funds released. "
                f"Current status: {investment.status}."
            )

        from services.investment_service import release_funds

        try:
            investment = release_funds(investment_id, actor=request.user)
        except ValueError as e:
            return _bad_request(str(e))

        # Fetch with snapshot relation for response
        investment = (
            Investment.objects
            .select_related("created_by", "fund_released_by", "snapshot")
            .get(pk=investment_id)
        )

        return Response(
            InvestmentDetailSerializer(investment).data,
            status=status.HTTP_200_OK,
        )


# ---------------------------------------------------------------------------
# Close investment: OPEN → CLOSED
# ---------------------------------------------------------------------------

class CloseInvestmentView(APIView):
    """
    POST /api/investments/{id}/close/

    FR-07:
      - Requires CLOSE_INVESTMENT permission.
      - Investment must be in OPEN status.
      - Accepts return_amount, close_date, optional closure_comment.
      - PnL is stored on the investment record.
      - Closed investment becomes read-only (editable only via reversal).
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, investment_id):
        if not _has_perm(request, PermissionCode.CLOSE_INVESTMENT):
            return _forbidden()

        investment = get_object_or_404(Investment, investment_id=investment_id)

        if investment.status != InvestmentStatus.OPEN:
            return _bad_request(
                f"Only OPEN investments can be closed. "
                f"Current status: {investment.status}."
            )

        serializer = CloseInvestmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        from services.investment_service import close_investment

        try:
            investment = close_investment(
                investment_id,
                actor=request.user,
                return_amount=serializer.validated_data["return_amount"],
                close_date=serializer.validated_data["close_date"],
                closure_comment=serializer.validated_data.get("closure_comment", ""),
            )
        except ValueError as e:
            return _bad_request(str(e))

        return Response(
            InvestmentDetailSerializer(investment).data,
            status=status.HTTP_200_OK,
        )


# ---------------------------------------------------------------------------
# Snapshot detail
# ---------------------------------------------------------------------------

class InvestmentSnapshotView(APIView):
    """
    GET /api/investments/{id}/snapshot/

    Returns the frozen member capital ratios for this investment.
    Available only after the investment has transitioned to OPEN.
    Any authenticated user can view (useful for transparency).
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, investment_id):
        investment = get_object_or_404(Investment, investment_id=investment_id)

        if investment.status == InvestmentStatus.DRAFT:
            return _bad_request(
                "Snapshot is not available for DRAFT investments. "
                "Release funds first to capture the snapshot."
            )

        try:
            
            snapshot = (
                InvestmentSnapshotHeader.objects
                .prefetch_related("lines__user")
                .select_related("created_by", "investment")
                .get(investment=investment)
            )
        except InvestmentSnapshotHeader.DoesNotExist:
            return Response(
                {"detail": "Snapshot not found for this investment.", "errors": None},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = SnapshotDetailSerializer(snapshot)
        return Response(serializer.data, status=status.HTTP_200_OK)