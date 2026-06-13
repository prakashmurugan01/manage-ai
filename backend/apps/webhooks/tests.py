from django.test import TestCase

from apps.webhooks.models import DataSyncLog, Event
from apps.webhooks.tasks import process_cross_module_event


class CrossModuleSyncTests(TestCase):
    def test_process_event_creates_sync_logs_for_dependent_modules(self):
        event = Event.objects.create(
            source_module="crm",
            event_type="customer.updated",
            entity_type="customer",
            entity_id="C-100",
            payload={"version": "1"},
        )

        result = process_cross_module_event(event.id)

        self.assertTrue(result["processed"])
        self.assertEqual(set(result["dependent_modules"]), {"erp", "projects"})
        self.assertEqual(DataSyncLog.objects.filter(entity_id="C-100").count(), 2)

    def test_conflict_sets_priority_resolution_metadata(self):
        Event.objects.create(
            source_module="erp",
            event_type="invoice.updated",
            entity_type="invoice",
            entity_id="INV-1",
            payload={"version": "2"},
        )
        event = Event.objects.create(
            source_module="crm",
            event_type="deal.updated",
            entity_type="deal",
            entity_id="INV-1",
            payload={"version": "1"},
        )

        process_cross_module_event(event.id)

        log = DataSyncLog.objects.get(source_module="crm", target_module="erp", entity_id="INV-1")
        self.assertTrue(log.conflict_detected)
        self.assertEqual(log.resolution_strategy, DataSyncLog.ResolutionStrategy.PRIORITY)
        self.assertIn("competing_events", log.metadata)
