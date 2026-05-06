# apps/submissions/urls.py

from django.urls import path
from .views import (
    SubmissionListCreateView,
    SubmissionDetailView,
    SubmissionAttachmentView,
    ApprovalQueueView,
    SubmissionHistoryView,
    ApproveSubmissionView,
    RejectSubmissionView,
)

urlpatterns = [
    # Member endpoints
    path("", SubmissionListCreateView.as_view(), name="submission-list-create"),
    path("<uuid:request_id>/", SubmissionDetailView.as_view(), name="submission-detail"),
    path("<uuid:request_id>/attachments/", SubmissionAttachmentView.as_view(), name="submission-attachments"),

    # Admin endpoints
    path("queue/",ApprovalQueueView.as_view(), name="submission-queue"),
    path("history/", SubmissionHistoryView.as_view(), name="submission-history"),
    path("<uuid:request_id>/approve/",ApproveSubmissionView.as_view(), name="submission-approve"),
    path("<uuid:request_id>/reject/",RejectSubmissionView.as_view(), name="submission-reject"),
]
