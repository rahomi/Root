from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from accounts.models import User, UserRole, UserStatus

# Auth serializers


class LoginSerializer(serializers.Serializer):
    contact_no = serializers.CharField()
    password = serializers.CharField(write_only=True, style={"input_type": "password"})

    def validate(self, data):
        user = authenticate(
            request=self.context.get("request"),
            username=data["contact_no"],  # USERNAME_FIELD is contact_no
            password=data["password"],
        )
        if not user:
            raise serializers.ValidationError("Invalid credentials.", code="authorization")
        if not user.is_active or user.status == UserStatus.INACTIVE:
            raise serializers.ValidationError("Account is inactive.", code="authorization")
        data["user"] = user
        return data


class TokenResponseSerializer(serializers.Serializer):
    """Shape of the response returned after a successful login."""
    access = serializers.CharField()
    refresh = serializers.CharField()
    user = serializers.SerializerMethodField()

    def get_user(self, obj):
        user = obj["user"]
        return {
            "user_id":    str(user.user_id),
            "full_name":  user.full_name,
            "contact_no": user.contact_no,
            "email":      user.email,
            "role":       user.role,
            "status":     user.status,
        }


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True, style={"input_type": "password"})
    new_password = serializers.CharField(write_only=True, style={"input_type": "password"})
    confirm_password = serializers.CharField(write_only=True, style={"input_type": "password"})

    def validate_current_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Current password is incorrect.")
        return value

    def validate(self, data):
        if data["new_password"] != data["confirm_password"]:
            raise serializers.ValidationError(
                {"confirm_password": "Passwords do not match."}
            )
        validate_password(data["new_password"], self.context["request"].user)
        return data

# User management serializers


class UserCreateSerializer(serializers.ModelSerializer):
    """
    Used by Super Admin to create a new user.
    Password is set explicitly — the user must change it on first login
    (enforced via must_change_password flag if added later).
    """
    password = serializers.CharField(
        write_only=True, style={"input_type": "password"}
    )

    class Meta:
        model = User
        fields = [
            "full_name", "contact_no", "email",
            "join_date", "role", "notes", "password",
        ]
        extra_kwargs = {
            "role": {"default": UserRole.MEMBER},
        }

    def validate_contact_no(self, value):
        if User.objects.filter(contact_no=value).exists():
            raise serializers.ValidationError(
                "A user with this contact number already exists."
            )
        return value

    def validate_email(self, value):
        if value and User.objects.filter(email=value).exists():
            raise serializers.ValidationError(
                "A user with this email already exists."
            )
        return value

    def validate_role(self, value):
        # Only Super Admin can create another Super Admin
        request = self.context.get("request")
        if value == UserRole.SUPER_ADMIN:
            if not request or request.user.role != UserRole.SUPER_ADMIN:
                raise serializers.ValidationError(
                    "Only a Super Admin can assign the Super Admin role."
                )
        return value

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user


class UserDetailSerializer(serializers.ModelSerializer):
    """
    Read-only view of a user — returned after create, login, and GET.
    """
    class Meta:
        model = User
        fields = [
            "user_id", "full_name", "contact_no", "email",
            "join_date", "role", "status", "notes",
            "created_at", "updated_at",
        ]
        read_only_fields = fields


class UserUpdateSerializer(serializers.ModelSerializer):
    """
    Profile update — used by both the user themselves and an admin.
    Role and status changes are restricted (handled in the view).
    """
    class Meta:
        model = User
        fields = ["full_name", "email", "contact_no", "notes"]

    def validate_contact_no(self, value):
        # Exclude current user from uniqueness check
        if User.objects.filter(contact_no=value).exclude(pk=self.instance.pk).exists():
            raise serializers.ValidationError(
                "A user with this contact number already exists."
            )
        return value

    def validate_email(self, value):
        if value and User.objects.filter(email=value).exclude(pk=self.instance.pk).exists():
            raise serializers.ValidationError(
                "A user with this email already exists."
            )
        return value


class AdminUserUpdateSerializer(UserUpdateSerializer):
    """
    Extended update for admins — also allows status and role changes.
    """
    class Meta(UserUpdateSerializer.Meta):
        fields = UserUpdateSerializer.Meta.fields + ["role", "status", "join_date"]

    def validate_role(self, value):
        request = self.context.get("request")
        if value == UserRole.SUPER_ADMIN and request.user.role != UserRole.SUPER_ADMIN:
            raise serializers.ValidationError(
                "Only a Super Admin can assign the Super Admin role."
            )
        return value