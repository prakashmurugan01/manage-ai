from rest_framework import permissions

from apps.erp.models import FinancialAccount, Invoice, JournalEntry, PurchaseOrder
from apps.erp.serializers import FinancialAccountSerializer, InvoiceSerializer, JournalEntrySerializer, PurchaseOrderSerializer
from apps.modules.api import BaseModuleViewSet


class InvoiceViewSet(BaseModuleViewSet):
    queryset = Invoice.objects.select_related("company")
    serializer_class = InvoiceSerializer
    permission_classes = [permissions.IsAuthenticated]
    search_fields = ["number", "company__name", "status"]
    ordering_fields = ["due_date", "total", "created_at"]


class PurchaseOrderViewSet(BaseModuleViewSet):
    queryset = PurchaseOrder.objects.select_related("approved_by")
    serializer_class = PurchaseOrderSerializer
    permission_classes = [permissions.IsAuthenticated]
    search_fields = ["po_number", "vendor", "approval_status"]
    ordering_fields = ["total", "created_at"]


class FinancialAccountViewSet(BaseModuleViewSet):
    queryset = FinancialAccount.objects.all()
    serializer_class = FinancialAccountSerializer
    permission_classes = [permissions.IsAuthenticated]
    search_fields = ["name", "type", "currency"]
    ordering_fields = ["name", "balance", "created_at"]


class JournalEntryViewSet(BaseModuleViewSet):
    queryset = JournalEntry.objects.select_related("debit_account", "credit_account")
    serializer_class = JournalEntrySerializer
    permission_classes = [permissions.IsAuthenticated]
    search_fields = ["description", "reference"]
    ordering_fields = ["date", "amount", "created_at"]

