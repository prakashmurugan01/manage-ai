from django.urls import path

from .views import DashboardAnalyticsView, PerformanceAnalyticsView

urlpatterns = [
    path("dashboard/", DashboardAnalyticsView.as_view(), name="analytics-dashboard"),
    path("performance/", PerformanceAnalyticsView.as_view(), name="analytics-performance"),
]
