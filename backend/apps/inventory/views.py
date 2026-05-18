from rest_framework import permissions

from apps.inventory.models import InventoryPurchaseOrder, Product, StockLevel, StockMovement
from apps.inventory.serializers import InventoryPurchaseOrderSerializer, ProductSerializer, StockLevelSerializer, StockMovementSerializer
from apps.modules.api import BaseModuleViewSet


class ProductViewSet(BaseModuleViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = [permissions.IsAuthenticated]
    search_fields = ["sku", "name", "category"]
    ordering_fields = ["sku", "name", "reorder_level", "created_at"]


class StockLevelViewSet(BaseModuleViewSet):
    queryset = StockLevel.objects.select_related("product")
    serializer_class = StockLevelSerializer
    permission_classes = [permissions.IsAuthenticated]
    search_fields = ["product__sku", "product__name", "warehouse"]
    ordering_fields = ["available_qty", "quantity", "last_updated", "created_at"]


class InventoryPurchaseOrderViewSet(BaseModuleViewSet):
    queryset = InventoryPurchaseOrder.objects.all()
    serializer_class = InventoryPurchaseOrderSerializer
    permission_classes = [permissions.IsAuthenticated]
    search_fields = ["supplier", "status"]
    ordering_fields = ["expected_delivery", "received_at", "created_at"]


class StockMovementViewSet(BaseModuleViewSet):
    queryset = StockMovement.objects.select_related("product")
    serializer_class = StockMovementSerializer
    permission_classes = [permissions.IsAuthenticated]
    search_fields = ["product__sku", "product__name", "movement_type", "warehouse", "reference_doc"]
    ordering_fields = ["moved_at", "quantity", "created_at"]

