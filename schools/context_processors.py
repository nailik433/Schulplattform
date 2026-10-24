from .views import get_current_student


def current_student(request):
    """Expose the logged-in student (if any) to all templates."""
    return {"current_student": get_current_student(request)}
