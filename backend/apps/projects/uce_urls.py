from rest_framework.routers import DefaultRouter

from apps.projects.uce_views import UCEMilestoneViewSet, UCEProjectViewSet, UCETaskViewSet, UCETimeEntryViewSet

router = DefaultRouter()
router.register("projects", UCEProjectViewSet, basename="uce-projects")
router.register("projects/milestones", UCEMilestoneViewSet, basename="uce-project-milestones")
router.register("projects/tasks", UCETaskViewSet, basename="uce-project-tasks")
router.register("projects/time-entries", UCETimeEntryViewSet, basename="uce-project-time-entries")

urlpatterns = router.urls

