from rest_framework import serializers

from apps.inventory.models import InventoryPurchaseOrder, Product, StockLevel, StockMovement


class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = "__all__"


class StockLevelSerializer(serializers.ModelSerializer):
    class Meta:
        model = StockLevel
        fields = "__all__"


class InventoryPurchaseOrderSerializer(serializers.ModelSerializer):
    class Meta:
        model = InventoryPurchaseOrder
        fields = "__all__"


class StockMovementSerializer(serializers.ModelSerializer):
    class Meta:
        model = StockMovement
        fields = "__all__"

