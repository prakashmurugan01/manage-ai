from django.contrib import admin

from .models import (
    ApprovalRequest,
    ApprovalStage,
    ApprovalTemplate,
    BusinessHours,
    Holiday,
    SLAPolicy,
    ServiceItem,
    Ticket,
    TicketActivity,
    TicketAttachment,
    TicketComment,
    WorkflowExecution,
    WorkflowTemplate,
)


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ("ticket_id", "title", "type", "status", "priority", "project", "requester", "assigned_to", "sla_due_at", "sla_breached", "updated_at")
    list_filter = ("type", "status", "priority", "sla_breached", "source")
    search_fields = ("ticket_id", "title", "description", "project__name", "requester__email", "assigned_to__email")
    filter_horizontal = ("related_tickets",)
    readonly_fields = ("ticket_id", "first_response_at", "resolved_at", "closed_at", "created_at", "updated_at")


@admin.register(TicketComment)
class TicketCommentAdmin(admin.ModelAdmin):
    list_display = ("ticket", "author", "is_internal", "created_at")
    list_filter = ("is_internal",)
    search_fields = ("ticket__ticket_id", "ticket__title", "author__email", "body")
    filter_horizontal = ("mentions",)


@admin.register(TicketAttachment)
class TicketAttachmentAdmin(admin.ModelAdmin):
    list_display = ("ticket", "caption", "uploaded_by", "file_size", "created_at")
    search_fields = ("ticket__ticket_id", "caption", "uploaded_by__email")


@admin.register(TicketActivity)
class TicketActivityAdmin(admin.ModelAdmin):
    list_display = ("ticket", "action", "field_changed", "actor", "timestamp")
    list_filter = ("action",)
    search_fields = ("ticket__ticket_id", "action", "field_changed")


admin.site.register(ServiceItem)
admin.site.register(SLAPolicy)
admin.site.register(BusinessHours)
admin.site.register(Holiday)
admin.site.register(WorkflowTemplate)
admin.site.register(WorkflowExecution)
admin.site.register(ApprovalTemplate)
admin.site.register(ApprovalRequest)
admin.site.register(ApprovalStage)
