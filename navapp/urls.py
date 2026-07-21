from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("healthz", views.healthz, name="healthz"),
    path("readyz", views.readyz, name="readyz"),
    path("funds/", views.fund_list, name="fund-list"),
    path("funds/new/", views.fund_edit, name="fund-create"),
    path("funds/<int:pk>/edit/", views.fund_edit, name="fund-edit"),
    path("funds/<int:fund_pk>/classes/new/", views.share_class_edit, name="share-class-create"),
    path(
        "funds/<int:fund_pk>/classes/<int:pk>/edit/",
        views.share_class_edit,
        name="share-class-edit",
    ),
    path("classes/<int:pk>/nav/", views.nav_history, name="nav-history"),
    path(
        "classes/<int:share_class_pk>/entry/",
        views.simple_entry,
        name="simple-entry",
    ),
    path(
        "classes/<int:share_class_pk>/nav/chart/<int:year>/",
        views.nav_year_chart,
        name="nav-year-chart",
    ),
    path("classes/<int:share_class_pk>/nav/new/", views.nav_edit, name="nav-create"),
    path(
        "classes/<int:share_class_pk>/nav/<int:pk>/edit/",
        views.nav_edit,
        name="nav-edit",
    ),
    path(
        "classes/<int:share_class_pk>/nav/<int:pk>/delete/",
        views.nav_delete,
        name="nav-delete",
    ),
    path("classes/<int:pk>/nav/import/", views.bulk_import, name="bulk-import"),
    path("reports/new/", views.report_create, name="report-create"),
    path("reports/", views.report_history, name="report-history"),
    path("reports/<int:pk>/review/", views.report_review, name="report-review"),
    path("reports/<int:pk>/rfr/refresh/", views.report_refresh_rfr, name="report-refresh-rfr"),
    path("reports/<int:pk>/rfr/manual/", views.report_manual_rfr, name="report-manual-rfr"),
    path("reports/<int:pk>/commentary/", views.report_commentary, name="report-commentary"),
    path("reports/<int:pk>/preview/", views.report_preview, name="report-preview"),
    path("reports/<int:pk>/chart/", views.report_chart, name="report-chart"),
    path("reports/<int:pk>/generate/", views.report_generate, name="report-generate"),
    path("reports/<int:pk>/finalize/", views.report_finalize, name="report-finalize"),
    path(
        "reports/<int:pk>/download/<str:file_type>/",
        views.report_download,
        name="report-download",
    ),
    path("settings/organization/", views.organization_settings, name="organization-settings"),
    path("audit/", views.audit_log, name="audit-log"),
]
