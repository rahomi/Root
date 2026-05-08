# services/snapshot_service.py

from decimal import Decimal, ROUND_HALF_UP
from django.db.models import Sum
from django.utils import timezone

from accounts.models import User, UserStatus
from ledger.models import MemberCapitalLedgerEntry
from snapshots.models import InvestmentSnapshotHeader, InvestmentSnapshotLine


RATIO_PRECISION   = Decimal("0.0000000001")   # 10 decimal places
RATIO_SUM_EPSILON = Decimal("0.0000001")      # tolerance for sum check


def capture_snapshot(investment, actor) -> InvestmentSnapshotHeader:
    """
    FR-06 / BR-01 / BR-06:
    Freeze the capital ratio of every member at the moment of OPEN transition.

    Rules strictly enforced:
      - Uses ONLY posted (authorized) ledger entries. Pending submissions
        are excluded by design — they are not in the ledger table.
      - Only members with capital > 0 are included in the snapshot.
      - Inactive members with remaining capital ARE included (BR-05).
      - Snapshot records are immutable post-creation (model-level guard).
      - sum(ratio) == 1.0 is verified after bulk_create (SRS gap fix).

    Must be called inside an existing transaction.atomic() block.

    Raises:
        ValueError — if total authorized capital is zero (cannot snapshot)
        ValueError — if ratio sum check fails (integrity violation)
    """

    # Authorized capital per member — sum of ALL posted ledger entries.
    # Pending submissions are not in the ledger table, so they are
    # excluded automatically without any explicit filter needed.
    balances = list(
        MemberCapitalLedgerEntry.objects
        .values("user_id")
        .annotate(capital=Sum("amount"))
        .filter(capital__gt=Decimal("0"))
        .order_by("-capital", "user_id")   # deterministic order
    )

    if not balances:
        raise ValueError(
            "Cannot capture snapshot: no members have positive authorized capital. "
            "Ensure at least one submission has been approved before releasing funds."
        )

    total_capital = sum(b["capital"] for b in balances)

    if total_capital <= Decimal("0"):
        raise ValueError(
            f"Cannot capture snapshot: total authorized capital is {total_capital}."
        )

    # Create the snapshot header
    header = InvestmentSnapshotHeader.objects.create(
        investment=investment,
        total_capital=total_capital,
        member_count=len(balances),
        snapshot_time=timezone.now(),
        created_by=actor,
    )

    # Build snapshot lines
    lines     = []
    ratio_sum = Decimal("0")

    for b in balances:
        ratio = (b["capital"] / total_capital).quantize(
            RATIO_PRECISION, rounding=ROUND_HALF_UP
        )
        ratio_sum += ratio
        lines.append(
            InvestmentSnapshotLine(
                snapshot=header,
                user_id=b["user_id"],
                capital_at_snapshot=b["capital"],
                ratio=ratio,
            )
        )

    # bulk_create skips model save() — that's intentional.
    # InvestmentSnapshotLine.save() raises ValueError on updates,
    # not on initial creation, so bulk_create is safe here.
    InvestmentSnapshotLine.objects.bulk_create(lines)

    # Post-write integrity assertion (SRS gap fix)
    deviation = abs(ratio_sum - Decimal("1"))
    if deviation > RATIO_SUM_EPSILON:
        # This should never happen with correct arithmetic —
        # if it does, it indicates a floating-point or DB precision bug.
        raise ValueError(
            f"Snapshot integrity check failed: "
            f"sum(ratio) = {ratio_sum} (deviation {deviation} exceeds {RATIO_SUM_EPSILON}). "
            f"Snapshot header {header.snapshot_id} was created but is invalid — "
            f"investigate immediately."
        )

    return header