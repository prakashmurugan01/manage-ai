from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ("email", "username", "role", "is_active", "is_staff", "last_login")
    list_filter = ("role", "is_active", "is_staff")
    search_fields = ("email", "username", "first_name", "last_name")
    ordering = ("email",)
    fieldsets = UserAdmin.fieldsets + (
        ("ManageAI Profile", {"fields": ("role", "department", "phone", "avatar", "last_seen_at", "face_login_enabled", "face_image", "face_enrolled_at")}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("ManageAI Profile", {"fields": ("email", "role", "department", "phone")}),
    )
