import uuid
from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from decimal import Decimal
from submissions.storage import generate_signed_url

"""Handles the member capital submission request flow. A request is always 
   PENDING until actioned. Approval is atomic — see services/submission_service.py. 
   Attachments use a junction table so multiple files can be attached per request"""


class RequestType(models.TextChoices):
    INSTALLMENT = 'INSTALLMENT', 'Installment'
    SUBMISSION = 'SUBMISSION',  'Capital Submission'


class PaymentChannel(models.TextChoices):
    HAND_CASH = 'HAND_CASH', 'Hand Cash'
    BKASH = 'BKASH',     'bKash'
    BANK = 'BANK',      'Bank Transfer'
    OTHER = 'OTHER',     'Other'


class RequestStatus(models.TextChoices):
    PENDING = 'PENDING',  'Pending'
    APPROVED = 'APPROVED', 'Approved'
    REJECTED = 'REJECTED', 'Rejected'


class FileAttachment(models.Model):
    file_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                     related_name='uploaded_files')
    mime_type = models.CharField(max_length=100)
    byte_size = models.PositiveIntegerField()
    storage_key = models.CharField(max_length=500)  # opaque S3/Cloudinary key
    original_filename = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    ALLOWED_MIME_TYPES = ['image/jpeg', 'image/png', 'application/pdf']
    MAX_BYTE_SIZE = 5 * 1024 * 1024  # 5 MB default

    class Meta:
        db_table = 'submissions_fileattachment'

    def get_signed_url(self, expires_in=3600):
        """Always return a signed, time-limited URL — never a public one."""
        return generate_signed_url(self.storage_key, expires_in)


class CapitalSubmissionRequest(models.Model):
    request_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                           related_name='submission_requests')
    request_type = models.CharField(max_length=20, choices=RequestType.choices)
    amount = models.DecimalField(max_digits=18, decimal_places=2,
                                             validators=[MinValueValidator(Decimal('0.01'))])
    requested_at = models.DateTimeField(auto_now_add=True)
    txn_date = models.DateField()  # date of the actual payment transaction (not the request creation date)
    payment_channel = models.CharField(max_length=20, choices=PaymentChannel.choices)
    external_reference = models.CharField(max_length=255, blank=True)  # trx ID / bank ref
    notes = models.TextField(blank=True)

    status = models.CharField(max_length=10, choices=RequestStatus.choices,
                                          default=RequestStatus.PENDING, db_index=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                           null=True, blank=True, related_name='reviewed_submissions')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)

    # Set on approve — points to the created ledger entry (FR-04)
    resulting_ledger = models.OneToOneField(
        'ledger.MemberCapitalLedgerEntry', on_delete=models.PROTECT,
        null=True, blank=True, related_name='source_submission'
    )

    class Meta:
        db_table = 'submissions_capitalsubmissionrequest'
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['status', 'requested_at']),
        ]
        ordering = ['-requested_at']

    def __str__(self):
        return f'{self.user} — {self.amount} BDT ({self.status})'


class SubmissionAttachment(models.Model):
    """Junction: one submission may have multiple attachments (SRS gap fix)."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    submission = models.ForeignKey(CapitalSubmissionRequest, on_delete=models.CASCADE,
                                    related_name='attachments')
    file = models.ForeignKey(FileAttachment, on_delete=models.PROTECT)
    attached_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'submissions_submissionattachment'
        unique_together = [('submission', 'file')]