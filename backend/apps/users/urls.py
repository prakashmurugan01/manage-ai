from rest_framework.routers import DefaultRouter

from apps.users.views import RoleViewSet, UserRoleAssignmentViewSet

router = DefaultRouter()
router.register("users/roles", RoleViewSet, basename="uce-roles")
router.register("users/role-assignments", UserRoleAssignmentViewSet, basename="uce-role-assignments")

urlpatterns = router.urls

