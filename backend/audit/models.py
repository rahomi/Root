import uuid
from django.db import models
from django.conf import settings

""" Audit log models for immutable, append-only record of all critical actions and changes.
Designed for accountability and traceability. Each log entry captures the entity, action, actor, timestamp, and before/after state. """


class AuditAction(models.TextChoices):
    CREATE = 'CREATE'
    UPDATE = 'UPDATE'
    APPROVE = 'APPROVE'
    REJECT = 'REJECT'
    RELEASE_FUNDS = 'RELEASE_FUNDS'
    CLOSE = 'CLOSE'
    DISTRIBUTE = 'DISTRIBUTE'
    REVERSE = 'REVERSE'
    LOGIN = 'LOGIN'
    LOGOUT = 'LOGOUT'
    GRANT_PERM = 'GRANT_PERM'
    REVOKE_PERM = 'REVOKE_PERM'
    DEACTIVATE_USER = 'DEACTIVATE_USER'


class AuditLog(models.Model):
    audit_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    entity_name = models.CharField(max_length=100)            # e.g. 'Investment'
    entity_id = models.CharField(max_length=50)              # str(uuid)
    action = models.CharField(max_length=30, choices=AuditAction.choices, db_index=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                     related_name='audit_actions')
    occurred_at = models.DateTimeField(auto_now_add=True, db_index=True)
    before_json = models.JSONField(null=True, blank=True)
    after_json = models.JSONField(null=True, blank=True)
    reason = models.TextField(blank=True)

    class Meta:
        db_table = 'audit_auditlog'
        indexes = [
            models.Index(fields=['entity_name', 'entity_id']),
            models.Index(fields=['actor', 'occurred_at']),
        ]
        ordering = ['-occurred_at']

    def save(self, *args, **kwargs):
        if self._state.adding is False:
            raise ValueError('Audit log entries are immutable.')
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError('Audit log entries cannot be deleted.')