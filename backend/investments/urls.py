# apps/investments/urls.py

from django.urls import path
from .views import (
    InvestmentListCreateView,
    InvestmentDetailView,
    ReleaseFundsView,
    CloseInvestmentView,
    InvestmentSnapshotView,
)

urlpatterns = [
    path("", InvestmentListCreateView.as_view(), name="investment-list-create"),
    path("<uuid:investment_id>/", InvestmentDetailView.as_view(), name="investment-detail"),
    path("<uuid:investment_id>/release-funds/", ReleaseFundsView.as_view(), name="investment-release-funds"),
    path("<uuid:investment_id>/close/", CloseInvestmentView.as_view(), name="investment-close"),
    path("<uuid:investment_id>/snapshot/", InvestmentSnapshotView.as_view(), name="investment-snapshot"),
]