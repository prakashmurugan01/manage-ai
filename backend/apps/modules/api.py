from rest_framework import viewsets
from rest_framework.response import Response


class BaseModuleViewSet(viewsets.ModelViewSet):
    ordering_fields = ["created_at", "updated_at"]

    def get_queryset(self):
        queryset = super().get_queryset().filter(is_deleted=False)
        if hasattr(queryset.model, "organization") and getattr(self.request.user, "company_id", None):
            queryset = queryset.filter(organization_id=self.request.user.company_id)
        return queryset

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        return Response({"success": True, "data": response.data, "meta": {}, "errors": []})

    def retrieve(self, request, *args, **kwargs):
        response = super().retrieve(request, *args, **kwargs)
        return Response({"success": True, "data": response.data, "meta": {}, "errors": []})

    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        return Response({"success": True, "data": response.data, "meta": {}, "errors": []}, status=response.status_code)

    def update(self, request, *args, **kwargs):
        response = super().update(request, *args, **kwargs)
        return Response({"success": True, "data": response.data, "meta": {}, "errors": []}, status=response.status_code)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.is_deleted = True
        instance.save(update_fields=["is_deleted", "updated_at"])
        return Response({"success": True, "data": {}, "meta": {}, "errors": []})

