import uuid
from django.db import models
from django.conf import settings

""" Permission models for permisson system. This system is designed to be 
flexible and extensible, allowing for fine-grained capability grants per user. """


class PermissionCode(models.TextChoices):
    """ Declare the allowed permission constants."""
    APPROVE_SUBMISSION = 'APPROVE_SUBMISSION'  # approve user-submitted content
    POST_ADMIN_LEDGER = 'POST_ADMIN_LEDGER'  # post entries to the administrative ledger
    CREATE_INVESTMENT = 'CREATE_INVESTMENT'  # create new investment opportunities
    RELEASE_INVESTMENT_FUNDS = 'RELEASE_INVESTMENT_FUNDS'  # release funds for investments
    CLOSE_INVESTMENT = 'CLOSE_INVESTMENT'  # close existing investment positions
    DISTRIBUTE_PL = 'DISTRIBUTE_PL'  # distribute profit and loss allocations
    REVERSE_DISTRIBUTION = 'REVERSE_DISTRIBUTION'  # reverse profit and loss allocations
    VIEW_ALL_REPORTS = 'VIEW_ALL_REPORTS'  # view all reports
    MANAGE_USERS = 'MANAGE_USERS'  # manage users


class Permission(models.Model):
    """Stable permission code catalog. Permissions are never deleted, 
    only marked inactive and superseded by new ones. Stores one row per permission type. 
    Prevents arbitrary name from bring created. """
    permission_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=60, unique=True, choices=PermissionCode.choices)
    description = models.CharField(max_length=255)

    class Meta:
        db_table = 'permissions_permission'
        ordering = ['code']

    def __str__(self):
        return self.code


class UserPermission(models.Model):
    """Fine-grained capability grant per user. Unique per (user, permission).
    Enables direct per user permission assignment without needing to define roles. 
    Supports temporary access. """

    user_permission_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    user = models.ForeignKey(  # the user receiving the permission grant
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='permission_grants'
    )
    permission = models.ForeignKey(  # the granted permission
        Permission, on_delete=models.PROTECT,
        related_name='grants'
    )
    granted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name='grants_made'
    )
    granted_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)  # SRS gap fix
    is_active = models.BooleanField(default=True)              # soft revoke
    revoked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='grants_revoked'
    )
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'permissions_userpermission'
        unique_together = [('user', 'permission')]
        indexes = [
            models.Index(fields=['user', 'is_active']),
        ]