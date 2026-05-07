# apps/submissions/views.py

import uuid
import os
from django.shortcuts import get_object_or_404
from django.db import transaction
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser

from accounts.models import UserStatus
from permissions.models import PermissionCode
from audit.utils import log_action

from .models import (
    CapitalSubmissionRequest,
    FileAttachment,
    SubmissionAttachment,
    RequestType,
    RequestStatus,
)
from .serializers import (
    SubmissionCreateSerializer,
    SubmissionDetailSerializer,
    QueueSubmissionSerializer,
    SubmissionHistorySerializer,
    AttachmentUploadSerializer,
    RejectSerializer,
)
from .storage import save_upload
from .submission_service import approve_submission, reject_submission


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


def _build_storage_key(user_id, filename):
    """Deterministic, collision-resistant path under MEDIA_ROOT/attachments/."""
    ext  = os.path.splitext(filename)[-1].lower()
    name = f"{uuid.uuid4().hex}{ext}"
    return f"attachments/{str(user_id)[:8]}/{name}"


# ---------------------------------------------------------------------------
# Member: list own + create submission
# ---------------------------------------------------------------------------

class SubmissionListCreateView(APIView):
    """
    GET  /api/submissions/         Member's own submission list
    POST /api/submissions/         Create a new submission request
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = (
            CapitalSubmissionRequest.objects
            .filter(user=request.user)
            .prefetch_related("attachments__file")
            .order_by("-requested_at")
        )
        # Optional status filter
        status_filter = request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter.upper())

        serializer = SubmissionDetailSerializer(
            qs, many=True, context={"request": request}
        )
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        if request.user.status == UserStatus.INACTIVE:
            return Response(
                {"detail": "Inactive accounts cannot submit requests.", "errors": None},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = SubmissionCreateSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        submission = serializer.save()

        log_action(
            "CapitalSubmissionRequest",
            submission.request_id,
            "CREATE",
            request.user,
            after={
                "amount":          str(submission.amount),
                "request_type":    submission.request_type,
                "payment_channel": submission.payment_channel,
            },
        )
        return Response(
            SubmissionDetailSerializer(submission, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


# ---------------------------------------------------------------------------
# Member: submission detail
# ---------------------------------------------------------------------------

class SubmissionDetailView(APIView):
    """
    GET /api/submissions/{request_id}/
    Members see only their own. Admins with APPROVE_SUBMISSION see all.
    """
    permission_classes = [IsAuthenticated]

    def _get_submission(self, request, request_id):
        qs = CapitalSubmissionRequest.objects.prefetch_related("attachments__file")
        submission = get_object_or_404(qs, request_id=request_id)

        # Access control: own record OR has approval permission
        is_own   = submission.user_id == request.user.user_id
        is_staff = _has_perm(request, PermissionCode.APPROVE_SUBMISSION)
        if not (is_own or is_staff):
            return None, _forbidden()
        return submission, None

    def get(self, request, request_id):
        submission, err = self._get_submission(request, request_id)
        if err:
            return err
        serializer = SubmissionDetailSerializer(
            submission, context={"request": request}
        )
        return Response(serializer.data, status=status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# Member: upload attachment to an existing PENDING submission
# ---------------------------------------------------------------------------

class SubmissionAttachmentView(APIView):
    """
    POST /api/submissions/{request_id}/attachments/
    Adds a file attachment to a PENDING submission.
    Only the submitting member can add attachments.
    """
    permission_classes = [IsAuthenticated]
    parser_classes     = [MultiPartParser, FormParser]

    def post(self, request, request_id):
        submission = get_object_or_404(
            CapitalSubmissionRequest,
            request_id=request_id,
            user=request.user,             # members can only touch their own
        )

        if submission.status != RequestStatus.PENDING:
            return Response(
                {
                    "detail": "Attachments can only be added to PENDING submissions.",
                    "errors": None,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        upload_serializer = AttachmentUploadSerializer(data=request.data)
        upload_serializer.is_valid(raise_exception=True)
        uploaded_file = upload_serializer.validated_data["file"]

        # Build a unique storage key and persist the file
        storage_key = _build_storage_key(request.user.user_id, uploaded_file.name)
        save_upload(uploaded_file, storage_key)

        # Create the FileAttachment record and link it
        with transaction.atomic():
            attachment = FileAttachment.objects.create(
                uploaded_by=request.user,
                mime_type=uploaded_file.content_type,
                byte_size=uploaded_file.size,
                storage_key=storage_key,
                original_filename=uploaded_file.name,
            )
            SubmissionAttachment.objects.create(
                submission=submission,
                file=attachment,
            )

        log_action(
            "CapitalSubmissionRequest",
            submission.request_id,
            "UPDATE",
            request.user,
            after={"attachment_added": str(attachment.file_id)},
        )

        from .serializers import FileAttachmentSerializer
        return Response(
            FileAttachmentSerializer(attachment, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


# ---------------------------------------------------------------------------
# Admin: approval queue
# ---------------------------------------------------------------------------

class ApprovalQueueView(APIView):
    """
    GET /api/submissions/queue/
    Returns all PENDING submissions ordered oldest-first.
    Requires APPROVE_SUBMISSION permission.
    Supports ?payment_channel= filter.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_perm(request, PermissionCode.APPROVE_SUBMISSION):
            return _forbidden()

        qs = (
            CapitalSubmissionRequest.objects
            .filter(status=RequestStatus.PENDING)
            .select_related("user")
            .prefetch_related("attachments__file")
            .order_by("requested_at")   # oldest first — FIFO queue
        )

        channel_filter = request.query_params.get("payment_channel")
        if channel_filter:
            qs = qs.filter(payment_channel=channel_filter.upper())

        serializer = QueueSubmissionSerializer(
            qs, many=True, context={"request": request}
        )
        return Response(
            {
                "count":   qs.count(),
                "results": serializer.data,
            },
            status=status.HTTP_200_OK,
        )


# ---------------------------------------------------------------------------
# Reviewed history: approved/rejected submissions
# ---------------------------------------------------------------------------

class SubmissionHistoryView(APIView):
    """
    GET /api/submissions/history/
    Returns reviewed submissions: APPROVED and REJECTED by default.
    Staff with APPROVE_SUBMISSION see all reviewed submissions.
    Members without that permission see only their own reviewed submissions.
    Optional filters:
      ?status=APPROVED|REJECTED
      ?request_type=INSTALLMENT|SUBMISSION
      ?user_id=<uuid>
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = (
            CapitalSubmissionRequest.objects
            .filter(status__in=[RequestStatus.APPROVED, RequestStatus.REJECTED])
            .select_related("user", "reviewed_by")
            .order_by("-reviewed_at", "-requested_at")
        )

        if not _has_perm(request, PermissionCode.APPROVE_SUBMISSION):
            qs = qs.filter(user=request.user)

        user_id_filter = request.query_params.get("user_id")
        if user_id_filter:
            try:
                user_id = uuid.UUID(user_id_filter)
            except ValueError:
                return Response(
                    {
                        "detail": "user_id must be a valid UUID.",
                        "errors": {"user_id": ["Invalid user_id filter."]},
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            qs = qs.filter(user__user_id=user_id)

        status_filter = request.query_params.get("status")
        if status_filter:
            status_filter = status_filter.upper()
            if status_filter not in [RequestStatus.APPROVED, RequestStatus.REJECTED]:
                return Response(
                    {
                        "detail": "status must be APPROVED or REJECTED.",
                        "errors": {"status": ["Invalid status filter."]},
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            qs = qs.filter(status=status_filter)

        request_type_filter = request.query_params.get("request_type")
        if request_type_filter:
            request_type_filter = request_type_filter.upper()
            if request_type_filter not in [RequestType.INSTALLMENT, RequestType.SUBMISSION]:
                return Response(
                    {
                        "detail": "request_type must be INSTALLMENT or SUBMISSION.",
                        "errors": {"request_type": ["Invalid request_type filter."]},
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            qs = qs.filter(request_type=request_type_filter)

        serializer = SubmissionHistorySerializer(qs, many=True)
        return Response(
            {
                "count": qs.count(),
                "results": serializer.data,
            },
            status=status.HTTP_200_OK,
        )


# ---------------------------------------------------------------------------
# Admin: approve a submission
# ---------------------------------------------------------------------------

class ApproveSubmissionView(APIView):
    """
    POST /api/submissions/{request_id}/approve/
    Atomically approves the request and creates exactly one ledger entry.
    Requires APPROVE_SUBMISSION permission.
    Body: {} (empty — no additional input required)
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, request_id):
        if not _has_perm(request, PermissionCode.APPROVE_SUBMISSION):
            return _forbidden()


        try:
            submission = approve_submission(request_id, authorizer=request.user)
        except CapitalSubmissionRequest.DoesNotExist:
            return Response(
                {"detail": "Submission request not found.", "errors": None},
                status=status.HTTP_404_NOT_FOUND,
            )
        except ValueError as e:
            return Response(
                {"detail": str(e), "errors": None},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            SubmissionDetailSerializer(submission, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )


# ---------------------------------------------------------------------------
# Admin: reject a submission
# ---------------------------------------------------------------------------

class RejectSubmissionView(APIView):
    """
    POST /api/submissions/{request_id}/reject/
    Rejects the request. No ledger entry created.
    Requires APPROVE_SUBMISSION permission.
    Body: { "rejection_reason": "..." }
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, request_id):
        if not _has_perm(request, PermissionCode.APPROVE_SUBMISSION):
            return _forbidden()

        serializer = RejectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            submission = reject_submission(
                request_id,
                authorizer=request.user,
                reason=serializer.validated_data["rejection_reason"],
            )
        except CapitalSubmissionRequest.DoesNotExist:
            return Response(
                {"detail": "Submission request not found.", "errors": None},
                status=status.HTTP_404_NOT_FOUND,
            )
        except ValueError as e:
            return Response(
                {"detail": str(e), "errors": None},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            SubmissionDetailSerializer(submission, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )
