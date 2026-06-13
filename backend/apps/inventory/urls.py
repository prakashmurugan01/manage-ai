from rest_framework.routers import DefaultRouter

from apps.inventory.views import InventoryPurchaseOrderViewSet, ProductViewSet, StockLevelViewSet, StockMovementViewSet

router = DefaultRouter()
router.register("inventory/products", ProductViewSet, basename="inventory-products")
router.register("inventory/stock-levels", StockLevelViewSet, basename="inventory-stock-levels")
router.register("inventory/purchase-orders", InventoryPurchaseOrderViewSet, basename="inventory-purchase-orders")
router.register("inventory/stock-movements", StockMovementViewSet, basename="inventory-stock-movements")

urlpatterns = router.urls

