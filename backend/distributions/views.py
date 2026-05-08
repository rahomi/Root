# apps/distributions/views.py

from django.shortcuts import get_object_or_404
from django.db import IntegrityError
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from permissions.models import PermissionCode
from investments.models import Investment, InvestmentStatus

from .models import InvestmentDistribution, DistributionStatus
from .serializers import (
    DistributeSerializer,
    ReverseDistributionSerializer,
    DistributionDetailSerializer,
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
# Distribute P/L
# ---------------------------------------------------------------------------

class DistributePnLView(APIView):
    """
    POST /api/investments/{investment_id}/distribute/

    FR-08: Post the P/L to all members using stored snapshot ratios.
    Requires DISTRIBUTE_PL permission.

    - Investment must be CLOSED.
    - Uses stored snapshot ratios — never live balances (BR-02).
    - Rounding: half-up to 2dp; remainder to highest-capital member (§4.4).
    - Idempotency: second attempt while POSTED raises 400 (BR-03).
    - Body: {} (empty — all data derived from the investment record).
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, investment_id):
        if not _has_perm(request, PermissionCode.DISTRIBUTE_PL):
            return _forbidden()

        investment = get_object_or_404(Investment, investment_id=investment_id)

        if investment.status != InvestmentStatus.CLOSED:
            return _bad_request(
                f"Investment must be CLOSED to distribute. "
                f"Current status: '{investment.status}'."
            )

        # Validate (empty) body
        serializer = DistributeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        from services.distribution_service import distribute_pnl

        try:
            distribution = distribute_pnl(investment_id, actor=request.user)
        except Investment.DoesNotExist:
            return Response(
                {"detail": "Investment not found.", "errors": None},
                status=status.HTTP_404_NOT_FOUND,
            )
        except (ValueError, IntegrityError) as e:
            return _bad_request(str(e))

        # Fetch with full relations for response
        distribution = (
            InvestmentDistribution.objects
            .prefetch_related("lines__user", "lines__ledger_entry")
            .select_related("posted_by", "reversed_by")
            .get(pk=distribution.distribution_id)
        )

        return Response(
            DistributionDetailSerializer(distribution).data,
            status=status.HTTP_201_CREATED,
        )


# ---------------------------------------------------------------------------
# View distribution
# ---------------------------------------------------------------------------

class DistributionDetailView(APIView):
    """
    GET /api/investments/{investment_id}/distribution/

    Returns the distribution record (POSTED or REVERSED) for this investment.
    Any authenticated user can view.
    If multiple exist (post + reversal), returns the most recent one.
    Use ?status=POSTED|REVERSED to filter.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, investment_id):
        investment = get_object_or_404(Investment, investment_id=investment_id)

        qs = (
            InvestmentDistribution.objects
            .filter(investment=investment)
            .prefetch_related("lines__user", "lines__ledger_entry")
            .select_related("posted_by", "reversed_by")
            .order_by("-posted_at")
        )

        status_filter = request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter.upper())

        distributions = list(qs)

        if not distributions:
            return Response(
                {"detail": "No distribution found for this investment.", "errors": None},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(
            DistributionDetailSerializer(distributions, many=True).data,
            status=status.HTTP_200_OK,
        )


# ---------------------------------------------------------------------------
# Reverse distribution
# ---------------------------------------------------------------------------

class ReverseDistributionView(APIView):
    """
    POST /api/investments/{investment_id}/reverse/

    FR-09 / BR-04:
    Reverse a POSTED distribution using compensating ledger entries.
    Requires REVERSE_DISTRIBUTION permission.

    - Investment must be DISTRIBUTED.
    - Compensating entries are created (negated amounts).
    - Original ledger entries are NEVER touched (append-only ledger).
    - After reversal, investment returns to CLOSED and can be re-distributed once.
    - Reason is required.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, investment_id):
        if not _has_perm(request, PermissionCode.REVERSE_DISTRIBUTION):
            return _forbidden()

        investment = get_object_or_404(Investment, investment_id=investment_id)

        if investment.status != InvestmentStatus.DISTRIBUTED:
            return _bad_request(
                f"Only DISTRIBUTED investments can be reversed. "
                f"Current status: '{investment.status}'."
            )

        serializer = ReverseDistributionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        from services.distribution_service import reverse_distribution

        try:
            distribution = reverse_distribution(
                investment_id,
                actor=request.user,
                reason=serializer.validated_data["reason"],
            )
        except Investment.DoesNotExist:
            return Response(
                {"detail": "Investment not found.", "errors": None},
                status=status.HTTP_404_NOT_FOUND,
            )
        except ValueError as e:
            return _bad_request(str(e))

        # Fetch with full relations
        distribution = (
            InvestmentDistribution.objects
            .prefetch_related("lines__user", "lines__ledger_entry")
            .select_related("posted_by", "reversed_by")
            .get(pk=distribution.distribution_id)
        )

        return Response(
            DistributionDetailSerializer(distribution).data,
            status=status.HTTP_200_OK,
        )