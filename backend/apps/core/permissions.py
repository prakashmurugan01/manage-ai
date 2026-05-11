from rest_framework.permissions import SAFE_METHODS, BasePermission


class Roles:
    SUPER_ADMIN = "SUPER_ADMIN"
    ADMIN = "ADMIN"
    DEVELOPER = "DEVELOPER"
    CLIENT = "CLIENT"


def has_role(user, *roles):
    return bool(user and user.is_authenticated and getattr(user, "role", None) in roles)


def is_admin_level(user):
    return has_role(user, Roles.SUPER_ADMIN, Roles.ADMIN) or bool(user and user.is_superuser)


class IsSuperAdmin(BasePermission):
    def has_permission(self, request, view):
        return has_role(request.user, Roles.SUPER_ADMIN) or bool(request.user and request.user.is_superuser)


class IsAdminLevel(BasePermission):
    def has_permission(self, request, view):
        return is_admin_level(request.user)


class ReadOnlyForAuthenticated(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.method in SAFE_METHODS)


class ProjectRBACPermission(BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.method in SAFE_METHODS:
            return True
        if getattr(view, "action", None) in {"push_git", "sync_git"} and has_role(request.user, Roles.DEVELOPER):
            return True
        return is_admin_level(request.user)

    def has_object_permission(self, request, view, obj):
        user = request.user
        if has_role(user, Roles.SUPER_ADMIN):
            return True
        if has_role(user, Roles.ADMIN):
            return obj.owner_id == user.id or obj.admins.filter(id=user.id).exists() or request.method in SAFE_METHODS
        if has_role(user, Roles.DEVELOPER):
            if getattr(view, "action", None) in {"push_git", "sync_git"}:
                return obj.developers.filter(id=user.id).exists() or obj.teams.filter(members=user).exists()
            return request.method in SAFE_METHODS and (obj.developers.filter(id=user.id).exists() or obj.teams.filter(members=user).exists())
        if has_role(user, Roles.CLIENT):
            return request.method in SAFE_METHODS and obj.client_id == user.id
        return False


class TaskRBACPermission(BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.method in SAFE_METHODS:
            return True
        if is_admin_level(request.user):
            return True
        return request.method in {"PATCH", "PUT"} and has_role(request.user, Roles.DEVELOPER)

    def has_object_permission(self, request, view, obj):
        if hasattr(obj, "task"):
            obj = obj.task
        user = request.user
        if is_admin_level(user):
            return True
        if has_role(user, Roles.DEVELOPER):
            return obj.assignee_id == user.id and request.method in {"GET", "HEAD", "OPTIONS", "PATCH", "PUT"}
        if has_role(user, Roles.CLIENT):
            return request.method in SAFE_METHODS and obj.project.client_id == user.id
        return False


class DocumentRBACPermission(BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.method in SAFE_METHODS:
            return True
        if has_role(request.user, Roles.DEVELOPER) and request.method == "POST":
            return True
        return is_admin_level(request.user)

    def has_object_permission(self, request, view, obj):
        user = request.user
        if is_admin_level(user):
            return True
        if has_role(user, Roles.DEVELOPER):
            return obj.visibility == "INTERNAL" and obj.project.developers.filter(id=user.id).exists()
        if has_role(user, Roles.CLIENT):
            return obj.visibility in {"CLIENT", "PUBLIC"} and obj.project.client_id == user.id
        return False
