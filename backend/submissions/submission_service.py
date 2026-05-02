from django.db import transaction
from django.utils import timezone

from submissions.models import CapitalSubmissionRequest, RequestStatus
from ledger.models import MemberCapitalLedgerEntry, EntryType, ReferenceType
from audit.utils import log_action


def approve_submission(request_id, authorizer) -> CapitalSubmissionRequest:
    """
    FR-04: Atomically approve a PENDING submission request.

    Within a single DB transaction:
      1. Lock the request row (prevents concurrent double-approval).
      2. Assert status is PENDING.
      3. Create exactly one immutable ledger entry.
      4. Update request status to APPROVED and link the ledger entry.
      5. Write an audit log entry.

    Raises:
        CapitalSubmissionRequest.DoesNotExist  — bad request_id
        ValueError                             — request is not PENDING
    """
    with transaction.atomic():
        req = (
            CapitalSubmissionRequest.objects
            .select_for_update()            # row-level lock
            .get(pk=request_id)
        )

        if req.status != RequestStatus.PENDING:
            raise ValueError(
                f"Cannot approve: request is already '{req.status}'."
            )

        # Create exactly one ledger entry (FR-04 — atomically)
        entry = MemberCapitalLedgerEntry.objects.create(
            user=req.user,
            entry_type=EntryType.SUBMISSION,
            amount=req.amount,
            txn_date=req.txn_date,
            reference_type=ReferenceType.SUBMISSION_REQUEST,
            reference_id=str(req.request_id),
            comment=(
                f"Approved {req.get_request_type_display()} "
                f"via {req.get_payment_channel_display()}"
            ),
            created_by=authorizer,
        )

        # Atomically update the request
        req.status           = RequestStatus.APPROVED
        req.reviewed_by      = authorizer
        req.reviewed_at      = timezone.now()
        req.resulting_ledger = entry
        req.save(update_fields=[
            "status", "reviewed_by", "reviewed_at", "resulting_ledger",
        ])

        log_action(
            "CapitalSubmissionRequest",
            req.request_id,
            "APPROVE",
            authorizer,
            before={"status": "PENDING"},
            after={
                "status":     "APPROVED",
                "ledger_id":  str(entry.ledger_id),
                "amount":     str(entry.amount),
            },
        )

    return req


def reject_submission(request_id, authorizer, reason: str) -> CapitalSubmissionRequest:
    """
    FR-04: Reject a PENDING submission request.

    No ledger entry is created.
    Raises:
        CapitalSubmissionRequest.DoesNotExist  — bad request_id
        ValueError                             — request is not PENDING
    """
    with transaction.atomic():
        req = (
            CapitalSubmissionRequest.objects
            .select_for_update()
            .get(pk=request_id)
        )

        if req.status != RequestStatus.PENDING:
            raise ValueError(
                f"Cannot reject: request is already '{req.status}'."
            )

        req.status           = RequestStatus.REJECTED
        req.reviewed_by      = authorizer
        req.reviewed_at      = timezone.now()
        req.rejection_reason = reason
        req.save(update_fields=[
            "status", "reviewed_by", "reviewed_at", "rejection_reason",
        ])

        log_action(
            "CapitalSubmissionRequest",
            req.request_id,
            "REJECT",
            authorizer,
            before={"status": "PENDING"},
            after={"status": "REJECTED"},
            reason=reason,
        )

    return req