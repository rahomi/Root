from django.contrib.auth.backends import ModelBackend


class RootPermissionBackend(ModelBackend):
    """
    Override Django's permission checks to use our 
    UserPermission table instead of Django's built-in model permissions.
    """
    def has_perm(self, user_obj, perm, obj=None):
        if user_obj is None or not user_obj.is_authenticated or not user_obj.is_active:
            return False

        if obj is not None:
            return False

        if user_obj.is_super_admin:
            return True

        # perm format: 'permissions.CODE' or just 'CODE'
        code = perm.split('.')[-1]
        return user_obj.has_permission(code)
