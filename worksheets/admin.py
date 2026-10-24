from django.contrib import admin

from .models import Assignment, AssignmentFile, Submission, SubmissionFile


class AssignmentFileInline(admin.TabularInline):
    model = AssignmentFile
    extra = 0
    readonly_fields = ("original_name", "size", "uploaded_at")


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "school_class",
        "due_date",
        "collect_submissions",
        "created_by",
        "created_at",
    )
    list_filter = ("school_class", "collect_submissions")
    search_fields = ("title", "description")
    inlines = [AssignmentFileInline]


class SubmissionFileInline(admin.TabularInline):
    model = SubmissionFile
    extra = 0
    readonly_fields = ("original_name", "size", "uploaded_at")


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = ("assignment", "student", "created_at", "updated_at")
    list_filter = ("assignment__school_class",)
    inlines = [SubmissionFileInline]
