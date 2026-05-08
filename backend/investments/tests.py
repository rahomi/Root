from decimal import Decimal

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User, UserRole
from ledger.models import EntryType, MemberCapitalLedgerEntry, ReferenceType
from permissions.models import Permission, PermissionCode, UserPermission
from submissions.models import (
    CapitalSubmissionRequest,
    PaymentChannel,
    RequestStatus,
    RequestType,
)

from .models import Investment, InvestmentStatus


class InvestmentLifecycleApiTests(APITestCase):
    def setUp(self):
        self.finance = User.objects.create_user(
            contact_no="01710000001",
            full_name="Finance Admin",
            password="pass12345",
            join_date="2026-01-01",
            role=UserRole.ADMIN,
        )
        self.accounts = User.objects.create_user(
            contact_no="01710000002",
            full_name="Accounts Admin",
            password="pass12345",
            join_date="2026-01-01",
            role=UserRole.ADMIN,
        )
        self.closer = User.objects.create_user(
            contact_no="01710000003",
            full_name="Closer Admin",
            password="pass12345",
            join_date="2026-01-01",
            role=UserRole.ADMIN,
        )
        self.member_a = User.objects.create_user(
            contact_no="01710000004",
            full_name="Member A",
            password="pass12345",
            join_date="2026-01-01",
            role=UserRole.MEMBER,
        )
        self.member_b = User.objects.create_user(
            contact_no="01710000005",
            full_name="Member B",
            password="pass12345",
            join_date="2026-01-01",
            role=UserRole.MEMBER,
        )

        self._grant(self.finance, PermissionCode.CREATE_INVESTMENT)
        self._grant(self.accounts, PermissionCode.RELEASE_INVESTMENT_FUNDS)
        self._grant(self.closer, PermissionCode.CLOSE_INVESTMENT)

        self._post_ledger(self.member_a, "11000.00")
        self._post_ledger(self.member_b, "9000.00")

        CapitalSubmissionRequest.objects.create(
            user=self.member_b,
            request_type=RequestType.SUBMISSION,
            amount=Decimal("5000.00"),
            txn_date="2026-02-01",
            payment_channel=PaymentChannel.BKASH,
            external_reference="PENDING-TRX",
            status=RequestStatus.PENDING,
        )

    def _grant(self, user, code):
        permission, _ = Permission.objects.get_or_create(
            code=code,
            defaults={"description": code},
        )
        UserPermission.objects.create(
            user=user,
            permission=permission,
            granted_by=self.finance if user != self.finance else None,
        )

    def _post_ledger(self, user, amount):
        return MemberCapitalLedgerEntry.objects.create(
            user=user,
            entry_type=EntryType.SUBMISSION,
            amount=Decimal(amount),
            txn_date="2026-01-10",
            reference_type=ReferenceType.MANUAL,
            reference_id="seed",
            comment="Seed capital",
            created_by=self.finance,
        )

    def _create_investment(self):
        self.client.force_authenticate(self.finance)
        response = self.client.post(
            reverse("investment-list-create"),
            {
                "title": "Root Fixed Deposit",
                "investment_type": "FIXED_DEPOSIT",
                "invested_to": "Bank",
                "invested_amount": "10000.00",
                "created_date": "2026-03-01",
                "comment": "Initial FD",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        return response.data["investment_id"]

    def test_create_draft_requires_create_investment_permission(self):
        self.client.force_authenticate(self.member_a)
        response = self.client.post(
            reverse("investment-list-create"),
            {
                "title": "Unauthorized",
                "investment_type": "OTHER",
                "invested_to": "Counterparty",
                "invested_amount": "1000.00",
                "created_date": "2026-03-01",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(Investment.objects.filter(title="Unauthorized").exists())

    def test_release_funds_opens_investment_and_freezes_authorized_capital_snapshot(self):
        investment_id = self._create_investment()

        self.client.force_authenticate(self.accounts)
        response = self.client.post(
            reverse("investment-release-funds", args=[investment_id]),
            {},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        investment = Investment.objects.get(pk=investment_id)
        self.assertEqual(investment.status, InvestmentStatus.OPEN)
        self.assertIsNotNone(investment.fund_released_at)
        self.assertEqual(investment.fund_released_by, self.accounts)

        snapshot_response = self.client.get(
            reverse("investment-snapshot", args=[investment_id])
        )
        self.assertEqual(snapshot_response.status_code, status.HTTP_200_OK)
        self.assertEqual(snapshot_response.data["total_capital"], "20000.00")
        self.assertEqual(snapshot_response.data["member_count"], 2)

        lines = {
            line["member_contact"]: line
            for line in snapshot_response.data["lines"]
        }
        self.assertEqual(lines[self.member_a.contact_no]["capital_at_snapshot"], "11000.00")
        self.assertEqual(lines[self.member_b.contact_no]["capital_at_snapshot"], "9000.00")
        self.assertEqual(lines[self.member_a.contact_no]["ratio"], "0.5500000000")
        self.assertEqual(lines[self.member_b.contact_no]["ratio"], "0.4500000000")

    def test_draft_edit_is_blocked_after_open(self):
        investment_id = self._create_investment()
        self.client.force_authenticate(self.accounts)
        self.client.post(reverse("investment-release-funds", args=[investment_id]), {})

        self.client.force_authenticate(self.finance)
        response = self.client.patch(
            reverse("investment-detail", args=[investment_id]),
            {"title": "Edited after open"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertNotEqual(
            Investment.objects.get(pk=investment_id).title,
            "Edited after open",
        )

    def test_close_open_investment_computes_profit_or_loss(self):
        investment_id = self._create_investment()
        self.client.force_authenticate(self.accounts)
        self.client.post(reverse("investment-release-funds", args=[investment_id]), {})

        self.client.force_authenticate(self.closer)
        response = self.client.post(
            reverse("investment-close", args=[investment_id]),
            {
                "return_amount": "11250.00",
                "close_date": timezone.localdate().isoformat(),
                "closure_comment": "Matured",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        investment = Investment.objects.get(pk=investment_id)
        self.assertEqual(investment.status, InvestmentStatus.CLOSED)
        self.assertEqual(investment.return_amount, Decimal("11250.00"))
        self.assertEqual(investment.pnl_amount, Decimal("1250.00"))
