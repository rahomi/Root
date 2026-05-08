# services/investment_service.py

from decimal import Decimal
from django.db import transaction
from django.utils import timezone

from investments.models import Investment, InvestmentStatus
from audit.utils import log_action
from services.snapshot_service import capture_snapshot


# ---------------------------------------------------------------------------
# Release funds: DRAFT → OPEN
# ---------------------------------------------------------------------------

def release_funds(investment_id, actor) -> Investment:
    """
    FR-06 + BR-08: Accounts confirms funds are available.
    Transitions investment DRAFT → OPEN and atomically captures snapshot.

    Business rules enforced:
      - Investment must be in DRAFT status.
      - Segregation of duties: actor cannot be the creator (SRS gap fix).
      - Snapshot is captured inside the same transaction.

    Raises:
        Investment.DoesNotExist  — bad investment_id
        ValueError               — wrong status or segregation violation
    """
    with transaction.atomic():
        inv = Investment.objects.select_for_update().get(pk=investment_id)

        if inv.status != InvestmentStatus.DRAFT:
            raise ValueError(
                f"Cannot release funds: investment is '{inv.status}', expected DRAFT."
            )

        # Segregation of duties (SRS gap fix — BR addition)
        if str(inv.created_by_id) == str(actor.user_id):
            raise ValueError(
                "Segregation of duties violation: the user who created this "
                "investment cannot also release its funds. "
                "A different user with RELEASE_INVESTMENT_FUNDS permission is required."
            )

        inv.fund_released_at = timezone.now()
        inv.fund_released_by = actor
        inv.status           = InvestmentStatus.OPEN
        inv.save(update_fields=[
            "fund_released_at", "fund_released_by", "status", "updated_at"
        ])

        # Capture snapshot atomically at OPEN transition (BR-01)
        capture_snapshot(inv, actor)

        log_action(
            "Investment", inv.investment_id, "RELEASE_FUNDS", actor,
            before={"status": InvestmentStatus.DRAFT},
            after={
                "status":           InvestmentStatus.OPEN,
                "fund_released_at": inv.fund_released_at.isoformat(),
                "fund_released_by": str(actor.user_id),
            },
        )

    return inv


# ---------------------------------------------------------------------------
# Close investment: OPEN → CLOSED
# ---------------------------------------------------------------------------

def close_investment(investment_id, actor, return_amount, close_date, closure_comment="") -> Investment:
    """
    FR-07: Closer enters the actual return amount.
    Computes and stores pnl_amount = return_amount - invested_amount.
    Transitions OPEN → CLOSED.

    Notes:
      - pnl_amount may be negative (loss scenario).
      - pnl_amount = 0 is valid (break-even, no-op distribution allowed).
      - Closed investment is read-only; only correctable via distribution reversal flow.

    Raises:
        Investment.DoesNotExist  — bad investment_id
        ValueError               — wrong status
    """
    with transaction.atomic():
        inv = Investment.objects.select_for_update().get(pk=investment_id)

        if inv.status != InvestmentStatus.OPEN:
            raise ValueError(
                f"Cannot close: investment is '{inv.status}', expected OPEN."
            )

        pnl = return_amount - inv.invested_amount

        inv.return_amount   = return_amount
        inv.pnl_amount      = pnl
        inv.close_date      = close_date
        inv.closure_comment = closure_comment
        inv.status          = InvestmentStatus.CLOSED
        inv.save(update_fields=[
            "return_amount", "pnl_amount", "close_date",
            "closure_comment", "status", "updated_at",
        ])

        log_action(
            "Investment", inv.investment_id, "CLOSE", actor,
            before={"status": InvestmentStatus.OPEN},
            after={
                "status":         InvestmentStatus.CLOSED,
                "return_amount":  str(return_amount),
                "pnl_amount":     str(pnl),
                "close_date":     str(close_date),
            },
        )

    return inv