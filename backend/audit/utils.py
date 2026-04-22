from .models import AuditLog


def log_action(entity_name, entity_id, action, actor,
               before=None, after=None, reason=''):
    AuditLog.objects.create(
        entity_name=entity_name,
        entity_id=str(entity_id),
        action=action,
        actor=actor,
        before_json=before,
        after_json=after,
        reason=reason,
    )