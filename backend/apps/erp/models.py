from django.conf import settings
from django.db import models

from apps.core.models import UCEModel


class Invoice(UCEModel):
    number = models.CharField(max_length=80, unique=True)
    company = models.ForeignKey("crm.Company", related_name="invoices", on_delete=models.SET_NULL, null=True, blank=True, db_index=True)
    line_items = models.JSONField(default=list)
    subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    tax = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=14, decimal_places=2, default=0, db_index=True)
    status = models.CharField(max_length=40, default="draft", db_index=True)
    due_date = models.DateField(null=True, blank=True, db_index=True)
    paid_at = models.DateTimeField(null=True, blank=True, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "due_date"]), models.Index(fields=["company", "status"])]

    def __str__(self):
        return self.number


class PurchaseOrder(UCEModel):
    po_number = models.CharField(max_length=80, unique=True)
    vendor = models.CharField(max_length=180, db_index=True)
    items = models.JSONField(default=list)
    total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    approval_status = models.CharField(max_length=40, default="pending", db_index=True)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="erp_approved_pos", on_delete=models.SET_NULL, null=True, blank=True, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.po_number


class FinancialAccount(UCEModel):
    name = models.CharField(max_length=160, db_index=True)
    type = models.CharField(max_length=60, db_index=True)
    balance = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    currency = models.CharField(max_length=3, default="USD", db_index=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class JournalEntry(UCEModel):
    date = models.DateField(db_index=True)
    debit_account = models.ForeignKey("erp.FinancialAccount", related_name="debit_entries", on_delete=models.PROTECT, db_index=True)
    credit_account = models.ForeignKey("erp.FinancialAccount", related_name="credit_entries", on_delete=models.PROTECT, db_index=True)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    description = models.TextField(blank=True)
    reference = models.CharField(max_length=140, blank=True, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-date", "-created_at"]

    def __str__(self):
        return self.reference or str(self.id)

