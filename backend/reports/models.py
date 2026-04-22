from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.db.models import Sum
from django.db.models.functions import Coalesce
from ledger.models import MemberCapitalLedgerEntry
from submissions.models import CapitalSubmissionRequest, RequestStatus


"""No models. Pure view layer that queries across apps. 
All views require either membership (for self-service) or 
VIEW_ALL_REPORTS permission (for staff views). CSV export is via Django's StreamingHttpResponse."""


@login_required
def member_statement(request):
    user = request.user
    # Authorized balance — from posted entries only (BR-06)
    entries = MemberCapitalLedgerEntry.objects.filter(
        user=user
    ).order_by('txn_date', 'created_at')

    # Pending requests — shown separately, never affect balance
    pending = CapitalSubmissionRequest.objects.filter(
        user=user, status=RequestStatus.PENDING
    ).order_by('-requested_at')

    current_balance = entries.aggregate(
        total=Coalesce(Sum('amount'), 0)
    )['total']

    return render(request, 'reports/member_statement.html', {
        'entries': entries,
        'pending': pending,
        'current_balance': current_balance,
    })