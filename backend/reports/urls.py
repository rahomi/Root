# apps/reports/urls.py

from django.urls import path
from .views import (
    # Member self-service
    MyStatementView,
    MyDistributionsView,

    # Staff reports
    AssociationSummaryView,
    MemberBalancesView,
    InvestmentRegisterView,
    DistributionLogsView,
    ApprovalQueueReportView,

    # CSV exports
    ExportMemberBalancesCSV,
    ExportInvestmentRegisterCSV,
    ExportDistributionLogsCSV,
    ExportMemberStatementCSV,
)

urlpatterns = [
    # ── Member self-service ───────────────────────────────────────────────
    path("my-statement/", MyStatementView.as_view(), name="report-my-statement"),
    path("my-distributions/", MyDistributionsView.as_view(), name="report-my-distributions"),

    # ── Staff reports ─────────────────────────────────────────────────────
    path("association-summary/", AssociationSummaryView.as_view(), name="report-association-summary"),
    path("member-balances/", MemberBalancesView.as_view(), name="report-member-balances"),
    path("investment-register/", InvestmentRegisterView.as_view(), name="report-investment-register"),
    path("distribution-logs/", DistributionLogsView.as_view(), name="report-distribution-logs"),
    path("approval-queue-report/", ApprovalQueueReportView.as_view(), name="report-approval-queue"),

    # ── CSV exports ───────────────────────────────────────────────────────
    path("export/member-balances/", ExportMemberBalancesCSV.as_view(), name="export-member-balances"),
    path("export/investment-register/", ExportInvestmentRegisterCSV.as_view(), name="export-investment-register"),
    path("export/distribution-logs/", ExportDistributionLogsCSV.as_view(), name="export-distribution-logs"),
    path("export/member-statement/<uuid:user_id>/", ExportMemberStatementCSV.as_view(), name="export-member-statement"),
]