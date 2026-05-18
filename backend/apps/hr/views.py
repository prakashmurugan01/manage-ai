from rest_framework import permissions

from apps.hr.models import Department, Employee, LeaveRequest, Payroll
from apps.hr.serializers import DepartmentSerializer, EmployeeSerializer, LeaveRequestSerializer, PayrollSerializer
from apps.modules.api import BaseModuleViewSet


class DepartmentViewSet(BaseModuleViewSet):
    queryset = Department.objects.select_related("head")
    serializer_class = DepartmentSerializer
    permission_classes = [permissions.IsAuthenticated]
    search_fields = ["name"]
    ordering_fields = ["name", "budget", "employee_count", "created_at"]


class EmployeeViewSet(BaseModuleViewSet):
    queryset = Employee.objects.select_related("department", "manager", "user")
    serializer_class = EmployeeSerializer
    permission_classes = [permissions.IsAuthenticated]
    search_fields = ["emp_code", "name", "email", "role", "department__name"]
    ordering_fields = ["name", "start_date", "salary", "created_at"]


class LeaveRequestViewSet(BaseModuleViewSet):
    queryset = LeaveRequest.objects.select_related("employee", "approved_by")
    serializer_class = LeaveRequestSerializer
    permission_classes = [permissions.IsAuthenticated]
    search_fields = ["employee__name", "type", "status"]
    ordering_fields = ["start_date", "end_date", "created_at"]


class PayrollViewSet(BaseModuleViewSet):
    queryset = Payroll.objects.select_related("employee")
    serializer_class = PayrollSerializer
    permission_classes = [permissions.IsAuthenticated]
    search_fields = ["employee__name", "period", "payment_status"]
    ordering_fields = ["period", "net", "processed_at", "created_at"]

