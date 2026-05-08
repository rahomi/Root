# services/distribution_service.py

from decimal import Decimal, ROUND_HALF_UP
from django.db import transaction
from django.utils import timezone

from investments.models import Investment, InvestmentStatus
from snapshots.models import InvestmentSnapshotLine
from distributions.models import (
    InvestmentDistribution,
    InvestmentDistributionLine,
    DistributionStatus,
)
from ledger.models import (
    MemberCapitalLedgerEntry,
    EntryType,
    ReferenceType,
)
from audit.utils import log_action

TWO_DP = Decimal("0.01")


# ---------------------------------------------------------------------------
# Distribute P/L (FR-08)
# ---------------------------------------------------------------------------

def distribute_pnl(investment_id, actor) -> InvestmentDistribution:
    """
    FR-08 / BR-02 / BR-03 / §4.3–4.4:

    Post P/L shares to all members using stored snapshot ratios.

    Algorithm (§4.3–4.4):
      1. Fetch snapshot lines ordered by -capital_at_snapshot, user_id
         (deterministic — highest capital first, lowest UUID on tie).
      2. raw_share(member) = snapshotRatio * investmentPnL
      3. Round each share to 2dp using ROUND_HALF_UP.
      4. roundedTotal = sum(roundedShare)
      5. remainder = investmentPnL - roundedTotal
      6. Apply remainder to the first member (highest capital).
      7. Bulk-create ledger entries (positive = profit, negative = loss).
      8. Bulk-create distribution lines.
      9. Mark investment DISTRIBUTED.

    Idempotency: A DB-level partial unique constraint prevents a second
    POSTED distribution for the same investment. Any attempt raises
    IntegrityError, caught here and surfaced as ValueError.

    Raises:
        Investment.DoesNotExist — bad investment_id
        ValueError              — wrong status / already distributed /
                                  snapshot missing / zero capital
    """
    with transaction.atomic():
        inv = Investment.objects.select_for_update().get(pk=investment_id)

        if inv.status != InvestmentStatus.CLOSED:
            raise ValueError(
                f"Investment must be CLOSED before distribution. "
                f"Current status: '{inv.status}'."
            )

        # Explicit idempotency check (better error than IntegrityError)
        if InvestmentDistribution.objects.filter(
            investment=inv, status=DistributionStatus.POSTED
        ).exists():
            raise ValueError(
                "A distribution has already been posted for this investment. "
                "Reverse it before re-distributing."
            )

        # Fetch the immutable snapshot (BR-02 — never use live balances)
        try:
            snapshot = inv.snapshot
        except Exception:
            raise ValueError(
                "No snapshot found for this investment. "
                "This should not happen for a CLOSED investment — contact support."
            )

        # Snapshot lines: deterministic order (highest capital, lowest user_id on tie)
        snap_lines = list(
            InvestmentSnapshotLine.objects
            .filter(snapshot=snapshot)
            .select_related("user")
            .order_by("-capital_at_snapshot", "user_id")
        )

        if not snap_lines:
            raise ValueError("Snapshot has no member lines — cannot distribute.")

        pnl = inv.pnl_amount   # may be positive, zero, or negative

        # ── Step 1: Compute raw rounded shares ────────────────────────────
        shares = [
            (line, (line.ratio * pnl).quantize(TWO_DP, rounding=ROUND_HALF_UP))
            for line in snap_lines
        ]

        # ── Step 2: Rounding reconciliation (§4.4) ────────────────────────
        rounded_total = sum(s for _, s in shares)
        remainder     = (pnl - rounded_total).quantize(TWO_DP)

        # Apply remainder to first member (highest capital — deterministic)
        if remainder != Decimal("0"):
            first_line, first_share = shares[0]
            shares[0] = (first_line, first_share + remainder)

        # ── Step 3: Create distribution header ────────────────────────────
        distribution = InvestmentDistribution.objects.create(
            investment=inv,
            snapshot=snapshot,
            pnl_amount=pnl,
            rounded_total=rounded_total,
            remainder_applied=remainder,
            status=DistributionStatus.POSTED,
            posted_by=actor,
        )

        # ── Step 4: Bulk-create ledger entries ────────────────────────────
        # bulk_create does NOT call save() — that is intentional.
        # MemberCapitalLedgerEntry.save() guards against updates on existing
        # records, not against initial creation via bulk_create.
        ledger_entries_to_create = [
            MemberCapitalLedgerEntry(
                user=line.user,
                entry_type=EntryType.DISTRIBUTION,
                amount=share,             # positive = profit, negative = loss
                txn_date=timezone.now().date(),
                reference_type=ReferenceType.INVESTMENT,
                reference_id=str(inv.investment_id),
                comment=f"P/L distribution: {inv.title}",
                created_by=actor,
            )
            for line, share in shares
        ]
        created_entries = MemberCapitalLedgerEntry.objects.bulk_create(
            ledger_entries_to_create
        )

        # ── Step 5: Bulk-create distribution lines ────────────────────────
        dist_lines = [
            InvestmentDistributionLine(
                distribution=distribution,
                user=line.user,
                ratio_used=line.ratio,
                share_amount=share,
                ledger_entry=entry,
            )
            for (line, share), entry in zip(shares, created_entries)
        ]
        InvestmentDistributionLine.objects.bulk_create(dist_lines)

        # ── Step 6: Advance investment status ─────────────────────────────
        inv.status = InvestmentStatus.DISTRIBUTED
        inv.save(update_fields=["status", "updated_at"])

        log_action(
            "Investment", inv.investment_id, "DISTRIBUTE", actor,
            before={"status": InvestmentStatus.CLOSED},
            after={
                "status":          InvestmentStatus.DISTRIBUTED,
                "pnl_amount":      str(pnl),
                "member_count":    len(shares),
                "rounded_total":   str(rounded_total),
                "remainder":       str(remainder),
                "distribution_id": str(distribution.distribution_id),
            },
        )

    return distribution


# ---------------------------------------------------------------------------
# Reverse distribution (FR-09)
# ---------------------------------------------------------------------------

def reverse_distribution(investment_id, actor, reason: str) -> InvestmentDistribution:
    """
    FR-09 / BR-04:

    Reverse a posted distribution by creating compensating ledger entries.
    Previous entries are NEVER deleted or modified — append-only ledger.

    Steps:
      1. Fetch and lock the investment (must be DISTRIBUTED).
      2. Fetch the single POSTED distribution.
      3. Lock the distribution row.
      4. For each distribution line: create a new ledger entry with
         negated share_amount (DISTRIBUTION_REVERSAL type).
      5. Mark the distribution REVERSED (posted_at / reversed_by / reversed_at).
      6. Advance investment to REVERSED status.
      7. After reversal, investment may be re-distributed once (FR-09).

    Raises:
        Investment.DoesNotExist     — bad investment_id
        ValueError                  — wrong status / no posted distribution
    """
    with transaction.atomic():
        inv = Investment.objects.select_for_update().get(pk=investment_id)

        if inv.status != InvestmentStatus.DISTRIBUTED:
            raise ValueError(
                f"Only DISTRIBUTED investments can be reversed. "
                f"Current status: '{inv.status}'."
            )

        # Fetch the active distribution
        try:
            dist = (
                InvestmentDistribution.objects
                .select_for_update()
                .prefetch_related("lines__user", "lines__ledger_entry")
                .get(investment=inv, status=DistributionStatus.POSTED)
            )
        except InvestmentDistribution.DoesNotExist:
            raise ValueError(
                "No active (POSTED) distribution found for this investment."
            )

        now = timezone.now()

        # ── Create compensating ledger entries ────────────────────────────
        compensating_entries_to_create = [
            MemberCapitalLedgerEntry(
                user=line.user,
                entry_type=EntryType.DISTRIBUTION_REVERSAL,
                amount=-(line.share_amount),   # negated — cancels the original
                txn_date=now.date(),
                reference_type=ReferenceType.INVESTMENT,
                reference_id=str(inv.investment_id),
                comment=f"Distribution reversal: {inv.title}. Reason: {reason}",
                created_by=actor,
            )
            for line in dist.lines.all()
        ]
        compensating_entries = MemberCapitalLedgerEntry.objects.bulk_create(
            compensating_entries_to_create
        )

        # ── Mark distribution as REVERSED ─────────────────────────────────
        dist.status      = DistributionStatus.REVERSED
        dist.reversed_by = actor
        dist.reversed_at = now
        dist.save(update_fields=["status", "reversed_by", "reversed_at"])

        # ── Advance investment to REVERSED ────────────────────────────────
        # FR-09: after reversal the investment may be re-distributed once.
        # Setting status to CLOSED re-enables the distribute endpoint.
        inv.status = InvestmentStatus.CLOSED
        inv.save(update_fields=["status", "updated_at"])

        log_action(
            "Investment", inv.investment_id, "REVERSE", actor,
            before={"status": InvestmentStatus.DISTRIBUTED},
            after={
                "status":          InvestmentStatus.CLOSED,
                "distribution_id": str(dist.distribution_id),
                "reason":          reason,
            },
            reason=reason,
        )

    return dist