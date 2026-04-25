# ---------------------------------------------------------------------------
# Custom exception handler — normalises all DRF error shapes into:
#   { "detail": "...", "errors": { "field": ["msg"] } }
# ---------------------------------------------------------------------------

from rest_framework.views import exception_handler


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if response is None:
        # Unhandled exception — let Django's 500 handler deal with it
        return None

    # Normalise the payload
    data = response.data

    if isinstance(data, dict):
        # Already a dict — pull out detail and errors
        detail = data.get("detail")
        if detail is None:
            non_field_errors = data.get("non_field_errors")
            if isinstance(non_field_errors, list) and non_field_errors:
                detail = non_field_errors[0]
            else:
                detail = "An error occurred."
        errors = {k: v for k, v in data.items() if k != "detail"}
        response.data = {
            "detail": str(detail) if not isinstance(detail, list) else detail[0],
            "errors": errors or None,
        }
    elif isinstance(data, list):
        response.data = {
            "detail": data[0] if data else "An error occurred.",
            "errors": None,
        }

    return response
