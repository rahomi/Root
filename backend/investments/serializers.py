from decimal import Decimal
from rest_framework import serializers

from accounts.models import User
from .models import Investment, InvestmentStatus, InvestmentType


# ---------------------------------------------------------------------------
# Shared user mini-serializer (used inside responses)
# ---------------------------------------------------------------------------

class UserMinimalSerializer(serializers.Serializer):
    user_id   = serializers.UUIDField()
    full_name = serializers.CharField()


# ---------------------------------------------------------------------------
# Create (Finance)
# ---------------------------------------------------------------------------

class InvestmentCreateSerializer(serializers.ModelSerializer):
    """
    FR-06: Finance creates an investment in DRAFT status.
    invested_amount must be positive. Status is always set to DRAFT.
    """
    class Meta:
        model  = Investment
        fields = [
            "title", "investment_type", "invested_to",
            "invested_amount", "created_date", "comment",
        ]

    def validate_invested_amount(self, value):
        if value <= Decimal("0"):
            raise serializers.ValidationError("Invested amount must be greater than zero.")
        return value

    def create(self, validated_data):
        return Investment.objects.create(
            **validated_data,
            status=InvestmentStatus.DRAFT,
            created_by=self.context["request"].user,
        )


# ---------------------------------------------------------------------------
# Update (only while in DRAFT)
# ---------------------------------------------------------------------------

class InvestmentUpdateSerializer(serializers.ModelSerializer):
    """
    Allows editing of a DRAFT investment only.
    Status and financial fields locked after OPEN — enforced in the view.
    """
    class Meta:
        model  = Investment
        fields = [
            "title", "investment_type", "invested_to",
            "invested_amount", "created_date", "comment",
        ]

    def validate_invested_amount(self, value):
        if value <= Decimal("0"):
            raise serializers.ValidationError("Invested amount must be greater than zero.")
        return value

    def validate(self, data):
        if self.instance.status != InvestmentStatus.DRAFT:
            raise serializers.ValidationError(
                f"Only DRAFT investments can be edited. "
                f"Current status: {self.instance.status}."
            )
        return data


# ---------------------------------------------------------------------------
# Detail (read — all statuses)
# ---------------------------------------------------------------------------

class InvestmentDetailSerializer(serializers.ModelSerializer):
    created_by      = UserMinimalSerializer(read_only=True)
    fund_released_by = serializers.SerializerMethodField()
    pnl_amount      = serializers.SerializerMethodField()
    has_snapshot    = serializers.SerializerMethodField()

    class Meta:
        model  = Investment
        fields = [
            "investment_id", "title", "investment_type", "invested_to",
            "invested_amount", "created_date", "comment", "status",
            "fund_released_at", "fund_released_by",
            "close_date", "return_amount", "pnl_amount", "closure_comment",
            "has_snapshot",
            "created_by", "created_at", "updated_at",
        ]
        read_only_fields = fields

    def get_fund_released_by(self, obj):
        if obj.fund_released_by:
            return {
                "user_id":   str(obj.fund_released_by.user_id),
                "full_name": obj.fund_released_by.full_name,
            }
        return None

    def get_pnl_amount(self, obj):
        """
        PnL = return_amount - invested_amount.
        Only meaningful after closure. Returns None while DRAFT/OPEN.
        """
        if obj.return_amount is not None:
            return obj.return_amount - obj.invested_amount
        return None

    def get_has_snapshot(self, obj):
        return hasattr(obj, "snapshot") and obj.snapshot is not None


# ---------------------------------------------------------------------------
# List (compact — no snapshot info)
# ---------------------------------------------------------------------------

class InvestmentListSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source="created_by.full_name", read_only=True)
    pnl_amount      = serializers.SerializerMethodField()

    class Meta:
        model  = Investment
        fields = [
            "investment_id", "title", "investment_type",
            "invested_to", "invested_amount", "created_date",
            "status", "return_amount", "pnl_amount",
            "created_by_name", "created_at",
        ]
        read_only_fields = fields

    def get_pnl_amount(self, obj):
        if obj.return_amount is not None:
            return obj.return_amount - obj.invested_amount
        return None


# ---------------------------------------------------------------------------
# Release funds action
# ---------------------------------------------------------------------------

class ReleaseFundsSerializer(serializers.Serializer):
    """
    Body for POST /api/investments/{id}/release-funds/
    No extra fields required — the actor is the authenticated user.
    Kept as a serializer for future extensibility (e.g. notes field).
    """
    pass


# ---------------------------------------------------------------------------
# Close investment action
# ---------------------------------------------------------------------------

class CloseInvestmentSerializer(serializers.Serializer):
    """
    FR-07: Closer enters the return amount and optional closure comment.
    PnL is computed by the service: pnl = return_amount - invested_amount.
    """
    return_amount   = serializers.DecimalField(max_digits=18, decimal_places=2)
    close_date      = serializers.DateField()
    closure_comment = serializers.CharField(required=False, allow_blank=True, default="")

    def validate_return_amount(self, value):
        # Return amount can be less than invested (loss scenario) but not negative total
        if value < Decimal("0"):
            raise serializers.ValidationError(
                "Return amount cannot be negative. "
                "For a total loss, set return_amount to 0.00."
            )
        return value


# ---------------------------------------------------------------------------
# Snapshot serializers
# ---------------------------------------------------------------------------

class SnapshotLineSerializer(serializers.Serializer):
    user_id             = serializers.UUIDField(source="user.user_id")
    full_name           = serializers.CharField(source="user.full_name")
    capital_at_snapshot = serializers.DecimalField(max_digits=18, decimal_places=2)
    ratio               = serializers.DecimalField(max_digits=18, decimal_places=10)
    ratio_percent       = serializers.SerializerMethodField()

    def get_ratio_percent(self, obj):
        return round(float(obj.ratio) * 100, 6)


class SnapshotDetailSerializer(serializers.Serializer):
    snapshot_id   = serializers.UUIDField()
    investment_id = serializers.UUIDField(source="investment.investment_id")
    total_capital = serializers.DecimalField(max_digits=18, decimal_places=2)
    member_count  = serializers.IntegerField()
    snapshot_time = serializers.DateTimeField()
    created_by    = UserMinimalSerializer()
    lines         = SnapshotLineSerializer(many=True)