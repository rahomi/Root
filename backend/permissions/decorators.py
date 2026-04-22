from functools import wraps
from django.core.exceptions import PermissionDenied


def require_permission(code: str):
    """View decorator that checks fine-grained permission."""
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                from django.contrib.auth.views import redirect_to_login
                return redirect_to_login(request.get_full_path())
            if not request.user.has_permission(code):
                raise PermissionDenied
            return view_func(request, *args, **kwargs)
        return wrapped
    return decorator