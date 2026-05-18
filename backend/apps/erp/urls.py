from rest_framework.routers import DefaultRouter

from apps.erp.views import FinancialAccountViewSet, InvoiceViewSet, JournalEntryViewSet, PurchaseOrderViewSet

router = DefaultRouter()
router.register("erp/invoices", InvoiceViewSet, basename="erp-invoices")
router.register("erp/purchase-orders", PurchaseOrderViewSet, basename="erp-purchase-orders")
router.register("erp/accounts", FinancialAccountViewSet, basename="erp-accounts")
router.register("erp/journal-entries", JournalEntryViewSet, basename="erp-journal-entries")

urlpatterns = router.urls

