from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase

from accounts.models import UserRole
from permissions.models import Permission, PermissionCode, UserPermission


User = get_user_model()


class SuperAdminPowerTests(TestCase):
    def test_super_admin_has_all_permissions_without_grants(self):
        user = User.objects.create_user(
            contact_no="01700000001",
            full_name="Super Admin",
            password="strong-pass-123",
            join_date=date(2024, 1, 1),
            role=UserRole.SUPER_ADMIN,
        )

        self.assertTrue(user.is_super_admin)
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.is_staff)
        self.assertTrue(user.has_permission(PermissionCode.MANAGE_USERS))

    def test_non_super_admin_still_requires_explicit_permission_grant(self):
        user = User.objects.create_user(
            contact_no="01700000002",
            full_name="Regular Admin",
            password="strong-pass-123",
            join_date=date(2024, 1, 1),
            role=UserRole.ADMIN,
        )

        self.assertFalse(user.has_permission(PermissionCode.MANAGE_USERS))

        permission = Permission.objects.create(
            code=PermissionCode.MANAGE_USERS,
            description="Manage users",
        )
        UserPermission.objects.create(
            user=user,
            permission=permission,
            granted_by=user,
        )

        self.assertTrue(user.has_permission(PermissionCode.MANAGE_USERS))

    def test_demoting_super_admin_removes_unrestricted_flags(self):
        user = User.objects.create_user(
            contact_no="01700000003",
            full_name="Former Super Admin",
            password="strong-pass-123",
            join_date=date(2024, 1, 1),
            role=UserRole.SUPER_ADMIN,
        )

        user.role = UserRole.ADMIN
        user.save()
        user.refresh_from_db()

        self.assertFalse(user.is_super_admin)
        self.assertFalse(user.is_superuser)
        self.assertFalse(user.is_staff)
