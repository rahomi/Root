from django.db import models
from accounts.models import User, UserStatus
from audit.utils import log_action


class ActiveMemberManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(status=UserStatus.ACTIVE)


class MemberProfile(User):
    """Proxy model for member-facing views and management."""
    objects = ActiveMemberManager()
    all_members = models.Manager()

    class Meta:
        proxy = True
        ordering = ['full_name']
        verbose_name = 'Member'

    def deactivate(self, actor):
        self.status = UserStatus.INACTIVE
        self.is_active = False
        self.save(update_fields=['status', 'is_active', 'updated_at'])
        log_action('User', self.pk, 'UPDATE', actor,
                   before={'status': 'ACTIVE'}, after={'status': 'INACTIVE'})