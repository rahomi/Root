# apps/distributions/serializers.py

from rest_framework import serializers
from .models import InvestmentDistribution, InvestmentDistributionLine


# ---------------------------------------------------------------------------
# Distribution line — per member share
# ---------------------------------------------------------------------------

class DistributionLineSerializer(serializers.ModelSerializer):
    user_id   = serializers.UUIDField(source="user.user_id", read_only=True)
    full_name = serializers.CharField(source="user.full_name", read_only=True)

    class Meta:
        model  = InvestmentDistributionLine
        fields = [
            "distribution_line_id",
            "user_id", "full_name",
            "ratio_used", "share_amount",
            "ledger_entry_id",
        ]
        read_only_fields = fields

    ledger_entry_id = serializers.UUIDField(source="ledger_entry.ledger_id", read_only=True)


# ---------------------------------------------------------------------------
# Distribution header — full detail
# ---------------------------------------------------------------------------

class DistributionDetailSerializer(serializers.ModelSerializer):
    posted_by   = serializers.SerializerMethodField()
    reversed_by = serializers.SerializerMethodField()
    lines       = DistributionLineSerializer(many=True, read_only=True)

    class Meta:
        model  = InvestmentDistribution
        fields = [
            "distribution_id",
            "investment_id",
            "snapshot_id",
            "pnl_amount",
            "rounded_total",
            "remainder_applied",
            "status",
            "posted_by", "posted_at",
            "reversed_by", "reversed_at",
            "lines",
        ]
        read_only_fields = fields

    def get_posted_by(self, obj):
        return {"user_id": str(obj.posted_by.user_id), "full_name": obj.posted_by.full_name}

    def get_reversed_by(self, obj):
        if obj.reversed_by:
            return {"user_id": str(obj.reversed_by.user_id), "full_name": obj.reversed_by.full_name}
        return None


# ---------------------------------------------------------------------------
# Distribute action — no body required
# ---------------------------------------------------------------------------

class DistributeSerializer(serializers.Serializer):
    """
    POST /api/investments/{id}/distribute/
    No input required — all data is derived from the closed investment
    and its stored snapshot. Kept as a serializer for future extensibility.
    """
    pass


# ---------------------------------------------------------------------------
# Reverse action
# ---------------------------------------------------------------------------

class ReverseDistributionSerializer(serializers.Serializer):
    """
    POST /api/investments/{id}/reverse/
    Reason is required to document why the distribution is being reversed.
    """
    reason = serializers.CharField(min_length=5, max_length=500)