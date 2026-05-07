from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import User, UserRole
from .models import EntryType, MemberCapitalLedgerEntry, ReferenceType


class AdminLedgerViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(
            contact_no="01700000001",
            full_name="Admin User",
            password="secret123",
            join_date="2026-01-01",
            role=UserRole.SUPER_ADMIN,
        )
        self.member = User.objects.create_user(
            contact_no="01700000002",
            full_name="Sabbir Rahman",
            password="secret123",
            join_date="2026-01-01",
        )
        self.other_member = User.objects.create_user(
            contact_no="01700000003",
            full_name="Tania Akter",
            password="secret123",
            join_date="2026-01-01",
        )

        self.submission = self._entry(
            user=self.member,
            entry_type=EntryType.SUBMISSION,
            amount="8000.00",
            txn_date="2026-04-17",
            reference_id="SR003",
            comment="Hand Cash",
        )
        self.distribution = self._entry(
            user=self.member,
            entry_type=EntryType.DISTRIBUTION,
            amount="22500.00",
            txn_date="2026-02-01",
            reference_type=ReferenceType.INVESTMENT,
            reference_id="INV001",
            comment="Textile Import Q1 - Profit",
        )
        self.withdrawal = self._entry(
            user=self.other_member,
            entry_type=EntryType.WITHDRAW,
            amount="-5000.00",
            txn_date="2026-03-01",
            reference_id="WD01",
            comment="Withdrawal",
        )

    def _entry(
        self,
        *,
        user,
        entry_type,
        amount,
        txn_date,
        reference_type=ReferenceType.MANUAL,
        reference_id="",
        comment="",
    ):
        return MemberCapitalLedgerEntry.objects.create(
            user=user,
            entry_type=entry_type,
            amount=Decimal(amount),
            txn_date=txn_date,
            reference_type=reference_type,
            reference_id=reference_id,
            comment=comment,
            created_by=self.admin,
        )

    def test_requires_view_all_reports_permission(self):
        self.client.force_authenticate(self.member)

        response = self.client.get("/api/ledger/admin/")

        self.assertEqual(response.status_code, 403)

    def test_admin_can_view_all_ledger_entries_with_totals(self):
        self.client.force_authenticate(self.admin)

        response = self.client.get("/api/ledger/admin/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["entry_count"], 3)
        self.assertEqual(response.data["total_in"], Decimal("30500.00"))
        self.assertEqual(response.data["total_out"], Decimal("5000.00"))
        self.assertEqual(response.data["entries"][0]["member_name"], "Sabbir Rahman")
        self.assertEqual(response.data["entries"][0]["reference_id"], "SR003")

    def test_admin_can_filter_by_entry_type_and_user(self):
        self.client.force_authenticate(self.admin)

        response = self.client.get(
            f"/api/ledger/admin/?entry_type=SUBMISSION&user_id={self.member.user_id}"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["entry_count"], 1)
        self.assertEqual(
            response.data["entries"][0]["ledger_id"],
            str(self.submission.ledger_id),
        )

    def test_admin_can_post_ledger_entry_by_contact_no(self):
        self.client.force_authenticate(self.admin)

        response = self.client.post(
            "/api/ledger/admin-post/",
            {
                "contact_no": self.member.contact_no,
                "entry_type": EntryType.SUBMISSION,
                "amount": "2500.00",
                "txn_date": "2026-05-07",
                "comment": "Cash deposit",
                "reference_id": "CASH-001",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        entry = MemberCapitalLedgerEntry.objects.get(reference_id="CASH-001")
        self.assertEqual(entry.user, self.member)
        self.assertEqual(entry.amount, Decimal("2500.00"))

    def test_admin_post_requires_member_identifier(self):
        self.client.force_authenticate(self.admin)

        response = self.client.post(
            "/api/ledger/admin-post/",
            {
                "entry_type": EntryType.SUBMISSION,
                "amount": "2500.00",
                "txn_date": "2026-05-07",
                "comment": "Cash deposit",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data["errors"]["member"],
            ["Provide either user_id or contact_no."],
        )

    def test_admin_post_rejects_mismatched_user_id_and_contact_no(self):
        self.client.force_authenticate(self.admin)

        response = self.client.post(
            "/api/ledger/admin-post/",
            {
                "user_id": str(self.other_member.user_id),
                "contact_no": self.member.contact_no,
                "entry_type": EntryType.SUBMISSION,
                "amount": "2500.00",
                "txn_date": "2026-05-07",
                "comment": "Cash deposit",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data["errors"]["member"],
            ["user_id and contact_no refer to different users."],
        )
