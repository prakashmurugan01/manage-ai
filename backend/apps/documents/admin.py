from django.contrib import admin

from .models import Document


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ("title", "project", "visibility", "category", "version", "uploaded_by", "updated_at")
    list_filter = ("visibility", "category", "extension")
    search_fields = ("title", "description", "project__name")
