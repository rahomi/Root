from decimal import Decimal
import uuid
from django.db import models
from django.conf import settings

"""The immutable financial record. Every entry here is permanent — 
no updates, no deletes. Reversals create new compensating entries. 
The member's current balance is always derived by aggregating SUM(amount) filtered to this user's posted entries.

Immutability rule: Override save() and delete() to raise ValueError if called on an existing record. 
Ledger entries are written once and never touched again."""


class EntryType(models.TextChoices):
    SUBMISSION = 'SUBMISSION',           'Capital Submission'
    WITHDRAW = 'WITHDRAW',             'Withdrawal'
    ADJUSTMENT = 'ADJUSTMENT',           'Admin Adjustment'
    DISTRIBUTION = 'DISTRIBUTION',         'P/L Distribution'
    DISTRIBUTION_REVERSAL = 'DISTRIBUTION_REVERSAL', 'Distribution Reversal'


class ReferenceType(models.TextChoices):
    INVESTMENT = 'INVESTMENT'
    MANUAL = 'MANUAL'
    SYSTEM = 'SYSTEM'
    SUBMISSION_REQUEST = 'SUBMISSION_REQUEST'


class LedgerEntryManager(models.Manager):
    def get_balance(self, user) -> 'Decimal':
        from django.db.models import Sum
        result = self.filter(user=user).aggregate(total=Sum('amount'))
        return result['total'] or 0


class MemberCapitalLedgerEntry(models.Model):
    ledger_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                       related_name='ledger_entries')
    entry_type = models.CharField(max_length=30, choices=EntryType.choices)
    amount = models.DecimalField(max_digits=18, decimal_places=2)  # signed
    currency = models.CharField(max_length=5, default='BDT')
    txn_date = models.DateField()

    reference_type = models.CharField(max_length=30, choices=ReferenceType.choices)
    reference_id = models.CharField(max_length=50, blank=True)  # polymorphic FK (app-enforced)

    comment = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                   related_name='ledger_entries_created')
    created_at = models.DateTimeField(auto_now_add=True)

    objects = LedgerEntryManager()

    class Meta:
        db_table = 'ledger_membercapitalledgerentry'
        indexes = [
            models.Index(fields=['user', 'txn_date']),
            models.Index(fields=['reference_type', 'reference_id']),
            models.Index(fields=['entry_type']),
        ]
        ordering = ['txn_date', 'created_at']

    def save(self, *args, **kwargs):
        if self._state.adding is False:
            raise ValueError('Ledger entries are immutable and cannot be updated.')
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError('Ledger entries are immutable and cannot be deleted.')