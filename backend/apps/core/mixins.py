from apps.audit.services import audit_event


class AuditModelViewSetMixin:
    audit_entity = None

    def _entity_name(self):
        return self.audit_entity or self.queryset.model.__name__

    def perform_create(self, serializer):
        instance = serializer.save()
        audit_event(self.request, "CREATE", self._entity_name(), instance.pk, {"repr": str(instance)})

    def perform_update(self, serializer):
        instance = serializer.save()
        audit_event(self.request, "UPDATE", self._entity_name(), instance.pk, {"repr": str(instance)})

    def perform_destroy(self, instance):
        pk = instance.pk
        label = str(instance)
        instance.delete()
        audit_event(self.request, "DELETE", self._entity_name(), pk, {"repr": label})
