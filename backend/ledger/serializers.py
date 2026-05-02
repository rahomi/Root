# apps/ledger/serializers.py

from decimal import Decimal
from rest_framework import serializers
from django.db.models import Sum

from accounts.models import User
from .models import (
    MemberCapitalLedgerEntry,
    EntryType,
    ReferenceType,
)


# ---------------------------------------------------------------------------
# Ledger entry — read
# ---------------------------------------------------------------------------

class LedgerEntrySerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(
        source="created_by.full_name", read_only=True
    )

    class Meta:
        model  = MemberCapitalLedgerEntry
        fields = [
            "ledger_id", "entry_type", "amount", "currency",
            "txn_date", "reference_type", "reference_id",
            "comment", "created_by_name", "created_at",
        ]
        read_only_fields = fields


# ---------------------------------------------------------------------------
# Member ledger statement (entries + running balance + pending total)
# ---------------------------------------------------------------------------

class LedgerStatementSerializer(serializers.Serializer):
    """
    Response shape for GET /api/ledger/
    Includes running balance computed from posted entries only.
    Pending submission requests are shown separately (not in balance).
    """
    current_balance   = serializers.DecimalField(max_digits=18, decimal_places=2)
    pending_total     = serializers.DecimalField(max_digits=18, decimal_places=2)
    entry_count       = serializers.IntegerField()
    entries           = LedgerEntrySerializer(many=True)


# ---------------------------------------------------------------------------
# Admin-direct ledger post
# ---------------------------------------------------------------------------

ADMIN_ALLOWED_ENTRY_TYPES = [
    EntryType.SUBMISSION,
    EntryType.WITHDRAW,
    EntryType.ADJUSTMENT,
]


class AdminLedgerPostSerializer(serializers.Serializer):
    """
    FR-05: Admin posts a direct ledger entry without a submission request.
    Allowed types: SUBMISSION, WITHDRAW, ADJUSTMENT.
    DISTRIBUTION and DISTRIBUTION_REVERSAL are system-generated — not allowed here.
    """
    user_id      = serializers.UUIDField()
    entry_type   = serializers.ChoiceField(
        choices=[(t, t) for t in ADMIN_ALLOWED_ENTRY_TYPES]
    )
    amount       = serializers.DecimalField(max_digits=18, decimal_places=2)
    txn_date     = serializers.DateField()
    comment      = serializers.CharField(min_length=1)
    reference_id = serializers.CharField(required=False, allow_blank=True, default="")

    def validate_user_id(self, value):
        try:
            user = User.objects.get(user_id=value)
        except User.DoesNotExist:
            raise serializers.ValidationError("No user found with this ID.")
        self._target_user = user
        return value

    def validate(self, data):
        # Withdrawals and adjustments can be negative — but the resulting
        # balance must not go below zero unless policy explicitly allows it.
        entry_type = data.get("entry_type")
        amount     = data.get("amount", Decimal("0"))

        if entry_type == EntryType.SUBMISSION and amount <= 0:
            raise serializers.ValidationError(
                {"amount": "SUBMISSION amount must be positive."}
            )

        if entry_type == EntryType.WITHDRAW and amount >= 0:
            raise serializers.ValidationError(
                {"amount": "WITHDRAW amount must be negative (e.g. -5000.00)."}
            )

        # Check resulting balance for withdrawals
        if entry_type == EntryType.WITHDRAW:
            user = self._target_user
            current = (
                MemberCapitalLedgerEntry.objects
                .filter(user=user)
                .aggregate(total=Sum("amount"))["total"]
                or Decimal("0")
            )
            if current + amount < 0:
                raise serializers.ValidationError(
                    {
                        "amount": (
                            f"Withdrawal of {abs(amount)} exceeds current balance "
                            f"of {current}. Post an ADJUSTMENT if an override is required."
                        )
                    }
                )
        return data