from django.contrib import admin

from .models import Assignment, AssignmentFile


class AssignmentFileInline(admin.TabularInline):
    model = AssignmentFile
    extra = 0
    readonly_fields = ("original_name", "size", "uploaded_at")


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = ("title", "school_class", "due_date", "created_by", "created_at")
    list_filter = ("school_class",)
    search_fields = ("title", "description")
    inlines = [AssignmentFileInline]
