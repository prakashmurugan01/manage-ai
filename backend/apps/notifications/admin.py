from django.contrib import admin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("title", "recipient", "type", "urgency", "is_read", "is_sent_email", "created_at")
    list_filter = ("type", "urgency", "is_read", "is_sent_email")
    search_fields = ("title", "message", "recipient__email")
