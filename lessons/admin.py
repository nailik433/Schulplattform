from django.contrib import admin

from .models import ApiKey, Lesson, LessonResult


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ("title", "school_class", "created_by", "created_at")
    list_filter = ("school_class",)
    search_fields = ("title",)


@admin.register(LessonResult)
class LessonResultAdmin(admin.ModelAdmin):
    list_display = ("lesson", "student", "score", "max_score", "completed", "updated_at")
    list_filter = ("completed", "lesson__school_class")


@admin.register(ApiKey)
class ApiKeyAdmin(admin.ModelAdmin):
    list_display = ("label", "teacher", "is_active", "created_at", "last_used_at")
    list_filter = ("is_active",)
    search_fields = ("teacher__email", "label")
    readonly_fields = ("key", "created_at", "last_used_at")
