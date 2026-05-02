from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path("api/", include("accounts.urls")),
    path("api/submission/", include("submissions.urls")),
    path("api/ledger/", include("ledger.urls")),
]
