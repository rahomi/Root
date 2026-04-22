import uuid
from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from decimal import Decimal

"""Investment lifecycle management. Finance creates a DRAFT. 
Accounts releases funds → OPEN (snapshot captured atomically). 
A permissioned closer enters return amount → CLOSED. 
Segregation-of-duties: the user who created the investment cannot release its funds.

Segregation of duties (SRS gap fix): fund_released_by must not equal created_by. Enforced in investment_service.release_funds() — not just a comment."""


class InvestmentType(models.TextChoices):
    FIXED_DEPOSIT = 'FIXED_DEPOSIT',  'Fixed Deposit'
    EQUITY = 'EQUITY',         'Equity / Shares'
    REAL_ESTATE = 'REAL_ESTATE',    'Real Estate'
    LENDING = 'LENDING',        'Lending / Loan'
    OTHER = 'OTHER',          'Other'


class InvestmentStatus(models.TextChoices):
    DRAFT = 'DRAFT',       'Draft'
    OPEN = 'OPEN',        'Open'
    CLOSED = 'CLOSED',     'Closed'
    DISTRIBUTED = 'DISTRIBUTED', 'Distributed'
    REVERSED = 'REVERSED',   'Reversed'


class Investment(models.Model):
    investment_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=300)
    investment_type = models.CharField(max_length=20, choices=InvestmentType.choices,
                                       default=InvestmentType.OTHER)  # SRS gap fix
    invested_to = models.CharField(max_length=300)             # counterparty / vehicle
    invested_amount = models.DecimalField(max_digits=18, decimal_places=2,
                                          validators=[MinValueValidator(Decimal('0.01'))])
    created_date = models.DateField()
    comment = models.TextField(blank=True)

    # Two-person control: Finance creates, Accounts releases
    fund_released_at = models.DateTimeField(null=True, blank=True)
    fund_released_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        null=True, blank=True, related_name='investments_released'
    )

    # Closure
    close_date = models.DateField(null=True, blank=True)
    return_amount = models.DecimalField(max_digits=18, decimal_places=2,
                                          null=True, blank=True)
    pnl_amount = models.DecimalField(max_digits=18, decimal_places=2,
                                          null=True, blank=True)
    closure_comment = models.TextField(blank=True)

    status = models.CharField(max_length=15, choices=InvestmentStatus.choices,
                                       default=InvestmentStatus.DRAFT, db_index=True)

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                        related_name='investments_created')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'investments_investment'
        indexes = [models.Index(fields=['status', 'created_date'])]
        ordering = ['-created_date']

    def __str__(self):
        return f'{self.title} ({self.status})'