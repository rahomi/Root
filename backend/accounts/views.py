from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.views import TokenRefreshView

from django.contrib.auth import update_session_auth_hash
from django.shortcuts import get_object_or_404

from accounts.models import User, UserStatus
from audit.utils import log_action
from permissions.models import PermissionCode
from .serializers import (
    LoginSerializer,
    LogoutSerializer,
    ChangePasswordSerializer,
    UserCreateSerializer,
    UserDetailSerializer,
    UserUpdateSerializer,
    AdminUserUpdateSerializer,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _require_permission(request, code: str) -> bool:
    """Returns True if the authenticated user holds the given permission."""
    return request.user.has_perm(f"permissions.{code}")


def _permission_denied():
    return Response(
        {"detail": "You do not have permission to perform this action."},
        status=status.HTTP_403_FORBIDDEN,
    )


# ---------------------------------------------------------------------------
# Auth views
# ---------------------------------------------------------------------------

class LoginView(APIView):
    """
    POST /api/auth/login/
    Public endpoint. Accepts contact_no + password.
    Returns JWT access + refresh tokens and basic user info.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data["user"]
        refresh = RefreshToken.for_user(user)

        log_action("User", user.user_id, "LOGIN", user)

        return Response(
            {
                "access":  str(refresh.access_token),
                "refresh": str(refresh),
                "user": {
                    "user_id":    str(user.user_id),
                    "full_name":  user.full_name,
                    "contact_no": user.contact_no,
                    "email":      user.email,
                    "role":       user.role,
                    "status":     user.status,
                },
            },
            status=status.HTTP_200_OK,
        )


class LogoutView(APIView):
    """
    POST /api/auth/logout/
    Blacklists the provided refresh token so it cannot be reused.
    The client must also discard the access token locally.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            token = RefreshToken(serializer.validated_data["refresh"])
            token.blacklist()
        except TokenError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        log_action("User", request.user.user_id, "LOGOUT", request.user)
        return Response({"detail": "Successfully logged out."}, status=status.HTTP_200_OK)


class ChangePasswordView(APIView):
    """
    POST /api/auth/change-password/
    Authenticated user changes their own password.
    Requires current password for confirmation.
    All existing refresh tokens for this user remain valid —
    if you want to invalidate them, also call /logout/ with each.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)

        user = request.user
        user.set_password(serializer.validated_data["new_password"])
        user.save(update_fields=["password", "updated_at"])

        # Keep current session valid (Django session auth)
        update_session_auth_hash(request, user)

        log_action(
            "User", user.user_id, "UPDATE", user,
            after={"password_changed": True},
        )
        return Response(
            {"detail": "Password changed successfully."},
            status=status.HTTP_200_OK,
        )


# ---------------------------------------------------------------------------
# User management views
# ---------------------------------------------------------------------------

class UserListCreateView(APIView):
    """
    GET  /api/users/  — list all users (MANAGE_USERS)
    POST /api/users/  — create a new user (MANAGE_USERS)
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _require_permission(request, PermissionCode.MANAGE_USERS):
            return _permission_denied()

        qs = User.objects.all().order_by("full_name")

        # Optional filters
        status_filter = request.query_params.get("status")
        role_filter = request.query_params.get("role")
        search = request.query_params.get("search")

        if status_filter:
            qs = qs.filter(status=status_filter)
        if role_filter:
            qs = qs.filter(role=role_filter)
        if search:
            qs = qs.filter(full_name__icontains=search)

        serializer = UserDetailSerializer(qs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        if not _require_permission(request, PermissionCode.MANAGE_USERS):
            return _permission_denied()

        serializer = UserCreateSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        log_action(
            "User", user.user_id, "CREATE", request.user,
            after={"contact_no": user.contact_no, "role": user.role},
        )
        return Response(
            UserDetailSerializer(user).data,
            status=status.HTTP_201_CREATED,
        )


class UserDetailView(APIView):
    """
    GET    /api/users/{user_id}/  — view profile (self or MANAGE_USERS)
    PATCH  /api/users/{user_id}/  — update profile (self or MANAGE_USERS)
    DELETE /api/users/{user_id}/  — deactivate (MANAGE_USERS only, not self)
    """
    permission_classes = [IsAuthenticated]

    def _get_user_or_404(self, user_id):
        return get_object_or_404(User, user_id=user_id)

    def _can_access(self, request, target_user) -> bool:
        """User can access their own record, or staff with MANAGE_USERS."""
        return (
            str(request.user.user_id) == str(target_user.user_id)
            or _require_permission(request, PermissionCode.MANAGE_USERS)
        )

    def get(self, request, user_id):
        user = self._get_user_or_404(user_id)
        if not self._can_access(request, user):
            return _permission_denied()

        serializer = UserDetailSerializer(user)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, request, user_id):
        user = self._get_user_or_404(user_id)
        if not self._can_access(request, user):
            return _permission_denied()

        is_admin = _require_permission(request, PermissionCode.MANAGE_USERS)
        serializer_class = AdminUserUpdateSerializer if is_admin else UserUpdateSerializer

        serializer = serializer_class(
            user, data=request.data, partial=True,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)

        before = UserDetailSerializer(user).data
        updated_user = serializer.save()
        after = UserDetailSerializer(updated_user).data

        log_action(
            "User", user.user_id, "UPDATE", request.user,
            before=dict(before), after=dict(after),
        )
        return Response(
            UserDetailSerializer(updated_user).data,
            status=status.HTTP_200_OK,
        )

    def delete(self, request, user_id):
        """
        Soft-delete (deactivate) only. Hard delete is never allowed.
        Cannot deactivate yourself.
        """
        if not _require_permission(request, PermissionCode.MANAGE_USERS):
            return _permission_denied()

        user = self._get_user_or_404(user_id)

        if str(request.user.user_id) == str(user.user_id):
            return Response(
                {"detail": "You cannot deactivate your own account."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if user.status == UserStatus.INACTIVE:
            return Response(
                {"detail": "User is already inactive."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        before_status = user.status
        user.status = UserStatus.INACTIVE
        user.is_active = False
        user.save(update_fields=["status", "is_active", "updated_at"])

        log_action(
            "User", user.user_id, "DEACTIVATE_USER", request.user,
            before={"status": before_status},
            after={"status": UserStatus.INACTIVE},
        )
        return Response(
            {"detail": f"User '{user.full_name}' has been deactivated."},
            status=status.HTTP_200_OK,
        )


class MeView(APIView):
    """
    GET   /api/auth/me/    — current user's own profile
    PATCH /api/auth/me/    — update own profile (no role/status changes)
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(
            UserDetailSerializer(request.user).data,
            status=status.HTTP_200_OK,
        )

    def patch(self, request):
        serializer = UserUpdateSerializer(
            request.user, data=request.data,
            partial=True, context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        before = UserDetailSerializer(request.user).data
        updated = serializer.save()
        after = UserDetailSerializer(updated).data

        log_action(
            "User", request.user.user_id, "UPDATE", request.user,
            before=dict(before), after=dict(after),
        )
        return Response(UserDetailSerializer(updated).data, status=status.HTTP_200_OK)
