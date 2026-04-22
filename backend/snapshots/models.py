import uuid
from django.db import models
from django.conf import settings


"""Frozen at the moment the investment transitions to OPEN. 
Capital ratios are stored — never recomputed. 
The sum(ratio) across all lines for a given snapshot must equal 1.0000000000 (enforced post-write in snapshot_service.py)."""

class InvestmentSnapshotHeader(models.Model):
    snapshot_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    investment = models.OneToOneField(
        'investments.Investment', on_delete=models.PROTECT,
        related_name='snapshot'
    )
    total_capital = models.DecimalField(max_digits=18, decimal_places=2)
    member_count = models.PositiveIntegerField()
    snapshot_time = models.DateTimeField()
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)

    class Meta:
        db_table = 'snapshots_investmentsnapshotheader'

    def save(self, *args, **kwargs):
        if self._state.adding is False:
            raise ValueError('Snapshot headers are immutable.')
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError('Snapshot headers cannot be deleted.')


class InvestmentSnapshotLine(models.Model):
    snapshot_line_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    snapshot = models.ForeignKey(InvestmentSnapshotHeader, on_delete=models.PROTECT,
                                            related_name='lines')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    capital_at_snapshot = models.DecimalField(max_digits=18, decimal_places=2)
    ratio = models.DecimalField(max_digits=18, decimal_places=10)

    class Meta:
        db_table = 'snapshots_investmentsnapshotline'
        unique_together = [('snapshot', 'user')]
        ordering = ['-capital_at_snapshot']

    def save(self, *args, **kwargs):
        if self._state.adding is False:
            raise ValueError('Snapshot lines are immutable.')
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError('Snapshot lines cannot be deleted.')