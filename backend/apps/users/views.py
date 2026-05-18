from rest_framework import permissions

from apps.modules.api import BaseModuleViewSet
from apps.users.models import Role, UserRoleAssignment
from apps.users.serializers import RoleSerializer, UserRoleAssignmentSerializer


class RoleViewSet(BaseModuleViewSet):
    queryset = Role.objects.all()
    serializer_class = RoleSerializer
    permission_classes = [permissions.IsAdminUser]
    search_fields = ["name", "display_name"]


class UserRoleAssignmentViewSet(BaseModuleViewSet):
    queryset = UserRoleAssignment.objects.select_related("user", "role")
    serializer_class = UserRoleAssignmentSerializer
    permission_classes = [permissions.IsAdminUser]
    search_fields = ["user__email", "role__name"]

