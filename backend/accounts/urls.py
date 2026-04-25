from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    LoginView,
    LogoutView,
    ChangePasswordView,
    MeView,
    UserListCreateView,
    UserDetailView,
)

urlpatterns = [
    # --- Auth ---
    path("auth/login/", LoginView.as_view(), name="auth-login"),
    path("auth/logout/", LogoutView.as_view(), name="auth-logout"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="auth-token-refresh"),
    path("auth/change-password/", ChangePasswordView.as_view(), name="auth-change-password"),
    path("auth/me/", MeView.as_view(), name="auth-me"),

    # --- User management (MANAGE_USERS) ---
    path("users/", UserListCreateView.as_view(), name="user-list-create"),
    path("users/<uuid:user_id>/", UserDetailView.as_view(), name="user-detail"),
]