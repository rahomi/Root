import uuid
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin

from permissions.models import UserPermission
import django.utils.timezone as tz


class UserRole(models.TextChoices):
    SUPER_ADMIN = 'SUPER_ADMIN', 'Super Admin'
    ADMIN = 'ADMIN', 'Admin'
    MEMBER = 'MEMBER', 'Member'


class UserStatus(models.TextChoices):
    ACTIVE = 'ACTIVE', 'Active'
    INACTIVE = 'INACTIVE', 'Inactive'


class UserManager(BaseUserManager):
    """Custom user manager to handle user creation with contact number as username."""
    def create_user(self, contact_no, full_name, password=None, **extra_fields):
        if not contact_no:
            raise ValueError('Contact number is required')
        user = self.model(contact_no=contact_no, full_name=full_name, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, contact_no, full_name, password=None, **extra_fields):
        extra_fields.setdefault('role', UserRole.SUPER_ADMIN)
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        if extra_fields['role'] != UserRole.SUPER_ADMIN:
            raise ValueError('Superuser must have role=SUPER_ADMIN')
        return self.create_user(contact_no, full_name, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """Custom user model for the system."""

    # Primary key
    user_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Identity
    full_name = models.CharField(max_length=200)
    contact_no = models.CharField(max_length=30, unique=True)
    email = models.EmailField(null=True, blank=True, unique=True)

    # Association fields
    join_date = models.DateField()
    role = models.CharField(max_length=20, choices=UserRole.choices, default=UserRole.MEMBER)
    status = models.CharField(max_length=10, choices=UserStatus.choices, default=UserStatus.ACTIVE)
    notes = models.TextField(blank=True)

    # Django auth requirements
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = 'contact_no'
    REQUIRED_FIELDS = ['full_name', 'join_date']

    class Meta:
        indexes = [models.Index(fields=['status'])]
        ordering = ['full_name']

    @property
    def is_super_admin(self) -> bool:
        return self.role == UserRole.SUPER_ADMIN or self.is_superuser

    def __str__(self):
        return f'{self.full_name} ({self.contact_no})'

    def save(self, *args, **kwargs):
        # Super admins are the single source of truth for unrestricted power.
        if self.role == UserRole.SUPER_ADMIN:
            self.is_staff = True
            self.is_superuser = True
        else:
            self.is_staff = False
            self.is_superuser = False
        super().save(*args, **kwargs)

    def has_permission(self, code: str) -> bool:
        """Check fine-grained capability. Always use this, never check role."""
        if self.is_super_admin:
            return True
        now = tz.now()
        return UserPermission.objects.filter(
            user=self,
            permission__code=code,
            is_active=True,
        ).filter(
            models.Q(expires_at__isnull=True) | models.Q(expires_at__gt=now)
        ).exists()
