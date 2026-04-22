import uuid
from django.db import models
from django.conf import settings


"""The P/L distribution engine. Uses stored snapshot ratios — never live balances. 
Enforces exactly one active distribution per investment. 
Reversal is compensating-entry based: old entries remain untouched, new offsetting entries are created."""


class DistributionStatus(models.TextChoices):
    POSTED = 'POSTED',   'Posted'
    REVERSED = 'REVERSED', 'Reversed'


class InvestmentDistribution(models.Model):
    distribution_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    investment = models.ForeignKey(
        'investments.Investment', on_delete=models.PROTECT,
        related_name='distributions'
    )
    snapshot = models.ForeignKey(
        'snapshots.InvestmentSnapshotHeader', on_delete=models.PROTECT
    )
    pnl_amount = models.DecimalField(max_digits=18, decimal_places=2)
    rounded_total = models.DecimalField(max_digits=18, decimal_places=2)
    remainder_applied = models.DecimalField(max_digits=18, decimal_places=2, default=0)

    status = models.CharField(max_length=10, choices=DistributionStatus.choices,
                                        default=DistributionStatus.POSTED)
    posted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                         related_name='distributions_posted')
    posted_at = models.DateTimeField(auto_now_add=True)
    reversed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                         null=True, blank=True, related_name='distributions_reversed')
    reversed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'distributions_investmentdistribution'
        # DB-level idempotency: only one POSTED distribution per investment
        constraints = [
            models.UniqueConstraint(
                fields=['investment'],
                condition=models.Q(status='POSTED'),
                name='unique_posted_distribution_per_investment'
            )
        ]


class InvestmentDistributionLine(models.Model):
    distribution_line_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    distribution = models.ForeignKey(InvestmentDistribution, on_delete=models.PROTECT,
                                             related_name='lines')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    ratio_used = models.DecimalField(max_digits=18, decimal_places=10)
    share_amount = models.DecimalField(max_digits=18, decimal_places=2)  # signed
    ledger_entry = models.ForeignKey(
        'ledger.MemberCapitalLedgerEntry', on_delete=models.PROTECT
    )

    class Meta:
        db_table = 'distributions_investmentdistributionline'
        unique_together = [('distribution', 'user')]