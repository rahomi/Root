# apps/distributions/urls.py
# Mounted under /api/investments/ in config/urls.py
# alongside the investment URLs already defined in Phase 3.

from django.urls import path
from .views import (
    DistributePnLView,
    DistributionDetailView,
    ReverseDistributionView,
)

urlpatterns = [
    path("<uuid:investment_id>/distribute/", DistributePnLView.as_view(), name="distribution-create"),
    path("<uuid:investment_id>/distribution/", DistributionDetailView.as_view(), name="distribution-detail"),
    path("<uuid:investment_id>/reverse/", ReverseDistributionView.as_view(), name="distribution-reverse"),
]