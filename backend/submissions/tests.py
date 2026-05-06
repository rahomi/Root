from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User, UserRole
from .models import (
    CapitalSubmissionRequest,
    PaymentChannel,
    RequestStatus,
    RequestType,
)


class SubmissionHistoryViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.member = User.objects.create_user(
            contact_no="01700000001",
            full_name="Sabbir Rahman",
            password="secret123",
            join_date="2026-01-01",
        )
        self.other_member = User.objects.create_user(
            contact_no="01700000002",
            full_name="Tania Akter",
            password="secret123",
            join_date="2026-01-01",
        )
        self.admin = User.objects.create_user(
            contact_no="01700000003",
            full_name="Admin User",
            password="secret123",
            join_date="2026-01-01",
            role=UserRole.SUPER_ADMIN,
        )

        self.own_approved = self._submission(
            user=self.member,
            request_type=RequestType.INSTALLMENT,
            amount="8000.00",
            status=RequestStatus.APPROVED,
        )
        self.other_rejected = self._submission(
            user=self.other_member,
            request_type=RequestType.SUBMISSION,
            amount="5000.00",
            status=RequestStatus.REJECTED,
            rejection_reason="Payment reference could not be verified.",
        )
        self._submission(
            user=self.member,
            request_type=RequestType.SUBMISSION,
            amount="1500.00",
            status=RequestStatus.PENDING,
        )

    def _submission(
        self,
        *,
        user,
        request_type,
        amount,
        status,
        rejection_reason="",
    ):
        reviewed_at = timezone.now() if status != RequestStatus.PENDING else None
        reviewed_by = self.admin if status != RequestStatus.PENDING else None
        return CapitalSubmissionRequest.objects.create(
            user=user,
            request_type=request_type,
            amount=Decimal(amount),
            txn_date="2026-04-17",
            payment_channel=PaymentChannel.BKASH,
            external_reference="TXN123",
            status=status,
            reviewed_at=reviewed_at,
            reviewed_by=reviewed_by,
            rejection_reason=rejection_reason,
        )

    def test_member_sees_only_own_reviewed_history(self):
        self.client.force_authenticate(self.member)

        response = self.client.get("/api/submission/history/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(
            response.data["results"][0]["request_id"],
            str(self.own_approved.request_id),
        )
        self.assertEqual(response.data["results"][0]["member_name"], "Sabbir Rahman")
        self.assertEqual(response.data["results"][0]["status"], RequestStatus.APPROVED)

    def test_staff_sees_all_reviewed_history_and_can_filter_status(self):
        self.client.force_authenticate(self.admin)

        response = self.client.get("/api/submission/history/?status=REJECTED")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(
            response.data["results"][0]["request_id"],
            str(self.other_rejected.request_id),
        )
        self.assertEqual(response.data["results"][0]["member_name"], "Tania Akter")
        self.assertEqual(response.data["results"][0]["status"], RequestStatus.REJECTED)
