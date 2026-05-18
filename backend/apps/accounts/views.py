from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import decorators, filters, parsers, status, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.generics import CreateAPIView, RetrieveUpdateAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.mixins import AuditModelViewSetMixin
from apps.core.permissions import IsSuperAdmin, Roles, has_role, is_admin_level
from apps.enterprise.models import FeatureFlag
from apps.notifications.services import notify_user

from .face import best_similarity, build_face_profile, image_hash
from .models import Team
from .serializers import CustomTokenObtainPairSerializer, RegisterSerializer, TeamSerializer, UserSerializer, UserWriteSerializer

User = get_user_model()


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer


class RegisterView(CreateAPIView):
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]
    parser_classes = [parsers.MultiPartParser, parsers.FormParser, parsers.JSONParser]

    def create(self, request, *args, **kwargs):
        data = request.data.copy()
        for key in ("face_images", "face_image", "images", "image"):
            data.pop(key, None)
        serializer = self.get_serializer(data=data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        face_files = request.FILES.getlist("face_images") or request.FILES.getlist("images")
        if not face_files and request.FILES.get("image"):
            face_files = [request.FILES["image"]]
        if face_files:
            hashes, checks = build_face_profile(face_files[:3])
            user.face_hash = hashes[0] if hashes else ""
            user.face_embeddings = hashes
            user.face_security_checks = checks
            user.face_login_enabled = bool(hashes)
            user.face_enrolled_at = timezone.now()
            user.save(update_fields=["face_hash", "face_embeddings", "face_security_checks", "face_login_enabled", "face_enrolled_at"])
        return Response(UserSerializer(user, context={"request": request}).data, status=status.HTTP_201_CREATED)


class MeView(RetrieveUpdateAPIView):
    serializer_class = UserWriteSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [parsers.MultiPartParser, parsers.FormParser, parsers.JSONParser]

    def get_object(self):
        self.request.user.last_seen_at = timezone.now()
        self.request.user.save(update_fields=["last_seen_at"])
        return self.request.user


class AvatarUploadView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [parsers.MultiPartParser, parsers.FormParser]

    def post(self, request, *args, **kwargs):
        avatar = request.FILES.get("avatar") or request.FILES.get("image")
        if not avatar:
            return Response({"avatar": "Profile image is required."}, status=status.HTTP_400_BAD_REQUEST)
        user = request.user
        user.avatar = avatar
        user.save(update_fields=["avatar"])
        return Response(UserSerializer(user, context={"request": request}).data)


def face_login_available(user=None):
    qs = FeatureFlag.objects.filter(key="face_login", is_enabled=True)
    company = getattr(user, "company", None)
    if company:
        qs = qs.filter(company=company) | FeatureFlag.objects.filter(key="face_login", company__isnull=True, is_enabled=True)
    return qs.exists()


class FaceEnrollView(CreateAPIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [parsers.MultiPartParser, parsers.FormParser]

    def post(self, request, *args, **kwargs):
        if not face_login_available(request.user):
            return Response({"detail": "Face login is disabled by settings."}, status=status.HTTP_403_FORBIDDEN)
        images = request.FILES.getlist("face_images") or request.FILES.getlist("images")
        if not images and request.FILES.get("image"):
            images = [request.FILES["image"]]
        if not images:
            return Response({"image": "At least one face image is required."}, status=status.HTTP_400_BAD_REQUEST)
        user = request.user
        hashes, checks = build_face_profile(images[:3])
        user.face_hash = hashes[0] if hashes else ""
        user.face_embeddings = hashes
        user.face_security_checks = checks
        first_image = images[0]
        first_image.seek(0)
        user.face_image = first_image
        enabled = str(request.data.get("enabled", "true")).lower() in {"1", "true", "yes", "on"}
        user.face_login_enabled = enabled
        user.face_enrolled_at = timezone.now()
        user.save(update_fields=["face_hash", "face_embeddings", "face_security_checks", "face_image", "face_login_enabled", "face_enrolled_at"])
        return Response({"face_login_enabled": user.face_login_enabled, "face_enrolled_at": user.face_enrolled_at, "face_security_checks": checks})


class FaceLoginView(CreateAPIView):
    permission_classes = [AllowAny]
    parser_classes = [parsers.MultiPartParser, parsers.FormParser]

    def post(self, request, *args, **kwargs):
        email = request.data.get("email", "").strip().lower()
        image = request.FILES.get("image")
        if not email or not image:
            return Response({"detail": "Email and live face image are required."}, status=status.HTTP_400_BAD_REQUEST)
        user = User.objects.filter(email__iexact=email, is_active=True).first()
        if not user or not user.face_login_enabled or not user.face_hash:
            return Response({"detail": "Face login is not enrolled for this account."}, status=status.HTTP_403_FORBIDDEN)
        if not face_login_available(user):
            return Response({"detail": "Face login is disabled by settings."}, status=status.HTTP_403_FORBIDDEN)
        stored_hashes = user.face_embeddings or ([user.face_hash] if user.face_hash else [])
        score = best_similarity(stored_hashes, image)
        if score < 82:
            return Response({"detail": "Face match failed.", "score": score}, status=status.HTTP_403_FORBIDDEN)
        user.last_login = timezone.now()
        user.save(update_fields=["last_login"])
        refresh = RefreshToken.for_user(user)
        return Response({
            "refresh": str(refresh),
            "access": str(refresh.access_token),
            "user": UserSerializer(user, context={"request": request}).data,
            "face_match_score": score,
        })


class UserViewSet(AuditModelViewSetMixin, viewsets.ModelViewSet):
    queryset = User.objects.all()
    parser_classes = [parsers.MultiPartParser, parsers.FormParser, parsers.JSONParser]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["email", "username", "first_name", "last_name", "department", "secret_id", "role_title", "skills"]
    ordering_fields = ["email", "role", "date_joined", "last_login"]
    ordering = ["email"]
    audit_entity = "User"

    def get_permissions(self):
        if self.action in {"list", "retrieve", "secret_lookup"}:
            return [IsAuthenticated()]
        return [IsAuthenticated()]

    def get_serializer_class(self):
        if self.action in {"create", "update", "partial_update"}:
            return UserWriteSerializer
        return UserSerializer

    def get_queryset(self):
        user = self.request.user
        qs = User.objects.all()
        approval_status = self.request.query_params.get("approval_status")
        if approval_status:
            qs = qs.filter(approval_status=approval_status.upper())
        if has_role(user, Roles.SUPER_ADMIN):
            return qs
        if getattr(user, "company_id", None):
            qs = qs.filter(company_id=user.company_id)
        if has_role(user, Roles.ADMIN):
            return qs.exclude(role=Roles.SUPER_ADMIN)
        if is_admin_level(user):
            return qs
        return qs.filter(id=user.id)

    def _assert_can_manage_user(self, target_user=None, role=None):
        actor = self.request.user
        role = role or getattr(target_user, "role", None)
        if has_role(actor, Roles.SUPER_ADMIN) or actor.is_superuser:
            return
        if has_role(actor, Roles.ADMIN) and role in {Roles.DEVELOPER, Roles.CLIENT}:
            return
        raise ValidationError("You can only manage developer and client users from the Admin Panel.")

    def perform_create(self, serializer):
        self._assert_can_manage_user(role=serializer.validated_data.get("role", Roles.CLIENT))
        serializer.save(company=serializer.validated_data.get("company") or getattr(self.request.user, "company", None))

    def perform_update(self, serializer):
        self._assert_can_manage_user(target_user=serializer.instance, role=serializer.validated_data.get("role", serializer.instance.role))
        serializer.save()

    def perform_destroy(self, instance):
        self._assert_can_manage_user(target_user=instance)
        instance.delete()

    @decorators.action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        target = self.get_object()
        self._assert_can_manage_user(target_user=target)
        target.approval_status = User.ApprovalStatus.APPROVED
        target.is_active = True
        target.rejection_reason = ""
        target.approved_by = request.user
        target.approved_at = timezone.now()
        target.suspended_at = None
        target.save(update_fields=["approval_status", "is_active", "rejection_reason", "approved_by", "approved_at", "suspended_at"])
        notify_user(
            target,
            "Your ManageAI account is approved",
            "Your account has been approved. Dashboard access is now unlocked.",
            sender=request.user,
            type="SUCCESS",
        )
        return Response(UserSerializer(target, context={"request": request}).data)

    @decorators.action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        target = self.get_object()
        self._assert_can_manage_user(target_user=target)
        target.approval_status = User.ApprovalStatus.REJECTED
        target.is_active = True
        target.rejection_reason = request.data.get("reason", "").strip()
        target.approved_by = None
        target.approved_at = None
        target.suspended_at = None
        target.save(update_fields=["approval_status", "is_active", "rejection_reason", "approved_by", "approved_at", "suspended_at"])
        notify_user(
            target,
            "Your ManageAI registration was rejected",
            target.rejection_reason or "Your account registration was reviewed and rejected.",
            sender=request.user,
            type="WARNING",
        )
        return Response(UserSerializer(target, context={"request": request}).data)

    @decorators.action(detail=True, methods=["post"])
    def suspend(self, request, pk=None):
        target = self.get_object()
        self._assert_can_manage_user(target_user=target)
        target.approval_status = User.ApprovalStatus.SUSPENDED
        target.is_active = False
        target.rejection_reason = request.data.get("reason", "").strip()
        target.suspended_at = timezone.now()
        target.save(update_fields=["approval_status", "is_active", "rejection_reason", "suspended_at"])
        notify_user(
            target,
            "Your ManageAI account was suspended",
            target.rejection_reason or "Your account access has been suspended by an administrator.",
            sender=request.user,
            type="ALERT",
        )
        return Response(UserSerializer(target, context={"request": request}).data)

    @decorators.action(detail=False, methods=["get", "post"], url_path="secret-lookup")
    def secret_lookup(self, request):
        secret_id = request.query_params.get("secret_id") or request.data.get("secret_id")
        if not secret_id:
            raise ValidationError({"secret_id": "Secret ID is required."})
        user = self.get_queryset().filter(secret_id__iexact=secret_id.strip()).first()
        if not user:
            raise ValidationError({"secret_id": "No developer or user profile found for this Secret ID."})
        return Response(UserSerializer(user, context={"request": request}).data)


class TeamViewSet(AuditModelViewSetMixin, viewsets.ModelViewSet):
    serializer_class = TeamSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "description", "members__email", "members__first_name", "members__last_name"]
    ordering_fields = ["name", "created_at", "updated_at", "max_members"]
    ordering = ["name"]
    audit_entity = "Team"

    def get_queryset(self):
        user = self.request.user
        qs = Team.objects.select_related("lead", "created_by").prefetch_related("members")
        if getattr(user, "company_id", None):
            qs = qs.filter(company_id=user.company_id)
        if is_admin_level(user):
            return qs
        if has_role(user, Roles.DEVELOPER):
            return qs.filter(members=user)
        return qs.none()

    def _assert_admin(self):
        if not is_admin_level(self.request.user):
            raise ValidationError("Only Admin and Super Admin can manage teams.")

    def perform_create(self, serializer):
        self._assert_admin()
        serializer.save(created_by=self.request.user, company=serializer.validated_data.get("company") or getattr(self.request.user, "company", None))

    def perform_update(self, serializer):
        self._assert_admin()
        serializer.save()

    def perform_destroy(self, instance):
        self._assert_admin()
        instance.delete()
