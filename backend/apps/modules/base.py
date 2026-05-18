class UCEModuleBase:
    module_id = ""
    display_name = ""
    version = "1.0.0"
    schema = {}
    supported_query_types = ["rest", "nl"]

    def register(self):
        from apps.core.models import ModuleRegistry

        ModuleRegistry.objects.update_or_create(
            module_id=self.module_id,
            defaults={
                "display_name": self.display_name,
                "version": self.version,
                "schema": self.get_schema(),
                "capabilities": {"query_types": self.supported_query_types},
                "health_status": self.health_check()["status"],
                "is_active": True,
            },
        )

    def search(self, query):
        raise NotImplementedError

    def get_schema(self):
        return self.schema

    def health_check(self):
        return {"status": "healthy"}

    def handle_event(self, event):
        return None

    def get_related(self, entity_id, target_module):
        return []

