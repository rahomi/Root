# apps/ledger/urls.py

from django.urls import path
from .views import (
    MemberLedgerView,
    AdminLedgerView,
    AdminMemberLedgerView,
    AdminLedgerPostView,
)

urlpatterns = [
    # Member: own statement
    path("", MemberLedgerView.as_view(), name="ledger-statement"),

    # Admin: all member ledger entries
    path("admin/", AdminLedgerView.as_view(), name="ledger-admin-list"),

    # Admin: view any member's ledger
    path("members/<uuid:user_id>/", AdminMemberLedgerView.as_view(), name="ledger-member-detail"),

    # Admin: direct post
    path("admin-post/", AdminLedgerPostView.as_view(), name="ledger-admin-post"),
]
