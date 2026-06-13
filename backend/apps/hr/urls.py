from rest_framework.routers import DefaultRouter

from apps.hr.views import DepartmentViewSet, EmployeeViewSet, LeaveRequestViewSet, PayrollViewSet

router = DefaultRouter()
router.register("hr/departments", DepartmentViewSet, basename="hr-departments")
router.register("hr/employees", EmployeeViewSet, basename="hr-employees")
router.register("hr/leave-requests", LeaveRequestViewSet, basename="hr-leave-requests")
router.register("hr/payroll", PayrollViewSet, basename="hr-payroll")

urlpatterns = router.urls

