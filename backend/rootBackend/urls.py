from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path("api/", include("accounts.urls")),
    path("api/submission/", include("submissions.urls")),
    path("api/ledger/", include("ledger.urls")),
    path("api/investments/", include("investments.urls")),
    path("api/investments/", include("distributions.urls")),  # includes distribution and reversal URLs
    path("api/reports/", include("reports.urls")),
]
