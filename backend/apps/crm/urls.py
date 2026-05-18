from rest_framework.routers import DefaultRouter

from apps.crm.views import ActivityViewSet, CompanyViewSet, ContactViewSet, DealViewSet

router = DefaultRouter()
router.register("crm/companies", CompanyViewSet, basename="crm-companies")
router.register("crm/contacts", ContactViewSet, basename="crm-contacts")
router.register("crm/deals", DealViewSet, basename="crm-deals")
router.register("crm/activities", ActivityViewSet, basename="crm-activities")

urlpatterns = router.urls

