# apps/submissions/serializers.py

import os
from decimal import Decimal
from django.conf import settings
from rest_framework import serializers

from accounts.models import User
from .models import (
    CapitalSubmissionRequest,
    FileAttachment,
    SubmissionAttachment,
    RequestType,
    PaymentChannel,
    RequestStatus,
)


# ---------------------------------------------------------------------------
# FileAttachment
# ---------------------------------------------------------------------------

class FileAttachmentSerializer(serializers.ModelSerializer):
    signed_url = serializers.SerializerMethodField()

    class Meta:
        model  = FileAttachment
        fields = [
            "file_id", "original_filename", "mime_type",
            "byte_size", "created_at", "signed_url",
        ]
        read_only_fields = fields

    def get_signed_url(self, obj):
        return obj.get_signed_url(expires_in=3600)


class AttachmentUploadSerializer(serializers.Serializer):
    """
    Validates the uploaded file before saving to local storage.
    Checks MIME type and size against settings.
    """
    file = serializers.FileField()

    def validate_file(self, value):
        allowed = getattr(
            settings, "ATTACHMENT_ALLOWED_TYPES",
            ["image/jpeg", "image/png", "application/pdf"],
        )
        max_bytes = getattr(settings, "ATTACHMENT_MAX_SIZE_BYTES", 5 * 1024 * 1024)

        mime = value.content_type
        if mime not in allowed:
            raise serializers.ValidationError(
                f"File type '{mime}' is not allowed. "
                f"Accepted: {', '.join(allowed)}"
            )
        if value.size > max_bytes:
            mb = max_bytes // (1024 * 1024)
            raise serializers.ValidationError(
                f"File size exceeds the {mb} MB limit."
            )
        return value


# ---------------------------------------------------------------------------
# Submission request — creation
# ---------------------------------------------------------------------------

class SubmissionCreateSerializer(serializers.ModelSerializer):
    """
    Used by a member to create a new capital submission request.
    Status is always PENDING on creation — never set by client.
    """
    class Meta:
        model  = CapitalSubmissionRequest
        fields = [
            "request_type", "amount", "txn_date",
            "payment_channel", "external_reference", "notes",
        ]
        extra_kwargs = {
            "external_reference": {"required": False, "allow_blank": True},
            "notes":              {"required": False, "allow_blank": True},
        }

    def validate_amount(self, value):
        if value <= Decimal("0"):
            raise serializers.ValidationError("Amount must be greater than zero.")
        return value

    def create(self, validated_data):
        user = self.context["request"].user
        return CapitalSubmissionRequest.objects.create(
            user=user,
            status=RequestStatus.PENDING,
            **validated_data,
        )


# ---------------------------------------------------------------------------
# Submission request — read (member view)
# ---------------------------------------------------------------------------

class SubmissionDetailSerializer(serializers.ModelSerializer):
    """
    Full detail of a single submission request.
    Includes nested attachments with signed URLs.
    """
    attachments    = serializers.SerializerMethodField()
    reviewed_by    = serializers.SerializerMethodField()
    resulting_ledger_id = serializers.SerializerMethodField()

    class Meta:
        model  = CapitalSubmissionRequest
        fields = [
            "request_id", "request_type", "amount", "txn_date",
            "payment_channel", "external_reference", "notes",
            "status", "requested_at",
            "reviewed_by", "reviewed_at", "rejection_reason",
            "resulting_ledger_id", "attachments",
        ]
        read_only_fields = fields

    def get_attachments(self, obj):
        junction_qs = obj.attachments.select_related("file").all()
        return FileAttachmentSerializer(
            [j.file for j in junction_qs], many=True, context=self.context
        ).data

    def get_reviewed_by(self, obj):
        if obj.reviewed_by:
            return {"user_id": str(obj.reviewed_by.user_id), "full_name": obj.reviewed_by.full_name}
        return None

    def get_resulting_ledger_id(self, obj):
        if obj.resulting_ledger:
            return str(obj.resulting_ledger.ledger_id)
        return None


# ---------------------------------------------------------------------------
# Approval queue — admin view
# ---------------------------------------------------------------------------

class QueueSubmissionSerializer(serializers.ModelSerializer):
    """
    Compact serializer for the admin approval queue.
    Includes member name, payment channel, and attachment count.
    """
    member_name       = serializers.CharField(source="user.full_name", read_only=True)
    member_contact    = serializers.CharField(source="user.contact_no", read_only=True)
    attachment_count  = serializers.SerializerMethodField()
    attachments       = serializers.SerializerMethodField()

    class Meta:
        model  = CapitalSubmissionRequest
        fields = [
            "request_id", "member_name", "member_contact",
            "request_type", "amount", "txn_date",
            "payment_channel", "external_reference", "notes",
            "requested_at", "status",
            "attachment_count", "attachments",
        ]
        read_only_fields = fields

    def get_attachment_count(self, obj):
        return obj.attachments.count()

    def get_attachments(self, obj):
        junction_qs = obj.attachments.select_related("file").all()
        return FileAttachmentSerializer(
            [j.file for j in junction_qs], many=True, context=self.context
        ).data


# ---------------------------------------------------------------------------
# Reviewed submission history
# ---------------------------------------------------------------------------

class SubmissionHistorySerializer(serializers.ModelSerializer):
    """
    Compact serializer for approved/rejected submission history.
    Designed for reviewed-list UI rows.
    """
    member_name = serializers.CharField(source="user.full_name", read_only=True)
    member_contact = serializers.CharField(source="user.contact_no", read_only=True)
    reviewed_by = serializers.SerializerMethodField()

    class Meta:
        model = CapitalSubmissionRequest
        fields = [
            "request_id", "member_name", "member_contact",
            "request_type", "amount", "txn_date",
            "payment_channel", "external_reference",
            "status", "reviewed_at", "reviewed_by", "rejection_reason",
        ]
        read_only_fields = fields

    def get_reviewed_by(self, obj):
        if obj.reviewed_by:
            return {
                "user_id": str(obj.reviewed_by.user_id),
                "full_name": obj.reviewed_by.full_name,
            }
        return None


# ---------------------------------------------------------------------------
# Approve / Reject actions
# ---------------------------------------------------------------------------

class ApproveSerializer(serializers.Serializer):
    """No body required — approval has no extra fields."""
    pass


class RejectSerializer(serializers.Serializer):
    rejection_reason = serializers.CharField(min_length=1)
