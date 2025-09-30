from functools import wraps

from flask import render_template


def set_active_page(page_name):
    """Decorator to automatically set active_page for routes"""

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Get the result from the original function
            result = f(*args, **kwargs)

            # If it's a Response object, return as-is
            if hasattr(result, "status_code"):
                return result

            # If it's a tuple (template, context), add active_page
            if isinstance(result, tuple):
                template, context = result
                context["active_page"] = page_name
                return render_template(template, **context)

            # If it's just a template string, render with active_page
            return render_template(result, active_page=page_name)

        return decorated_function

    return decorator
