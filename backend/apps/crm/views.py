from rest_framework import permissions

from apps.crm.models import Activity, Company, Contact, Deal
from apps.crm.serializers import ActivitySerializer, CompanySerializer, ContactSerializer, DealSerializer
from apps.modules.api import BaseModuleViewSet


class CompanyViewSet(BaseModuleViewSet):
    queryset = Company.objects.all()
    serializer_class = CompanySerializer
    permission_classes = [permissions.IsAuthenticated]
    search_fields = ["name", "industry", "status"]
    ordering_fields = ["name", "annual_revenue", "created_at"]


class ContactViewSet(BaseModuleViewSet):
    queryset = Contact.objects.select_related("company", "assigned_to")
    serializer_class = ContactSerializer
    permission_classes = [permissions.IsAuthenticated]
    search_fields = ["name", "email", "company__name", "tags"]
    ordering_fields = ["name", "last_activity", "total_spend", "created_at"]


class DealViewSet(BaseModuleViewSet):
    queryset = Deal.objects.select_related("company", "assigned_to", "linked_project")
    serializer_class = DealSerializer
    permission_classes = [permissions.IsAuthenticated]
    search_fields = ["title", "company__name", "stage"]
    ordering_fields = ["value", "expected_close", "created_at"]


class ActivityViewSet(BaseModuleViewSet):
    queryset = Activity.objects.select_related("contact", "deal", "created_by")
    serializer_class = ActivitySerializer
    permission_classes = [permissions.IsAuthenticated]
    search_fields = ["notes", "outcome", "contact__name", "deal__title"]
    ordering_fields = ["activity_date", "created_at"]

