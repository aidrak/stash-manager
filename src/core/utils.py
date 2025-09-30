from flask import g


def set_active_page(page_name):
    """Set the active page for template rendering"""
    try:
        g.active_page = page_name
    except RuntimeError:
        # Outside application context, ignore
        pass
