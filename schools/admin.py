from django.contrib import admin

from .models import ClassMembership, School, SchoolClass, Student


class ClassMembershipInline(admin.TabularInline):
    model = ClassMembership
    extra = 0
    autocomplete_fields = ("teacher",)


@admin.register(School)
class SchoolAdmin(admin.ModelAdmin):
    list_display = ("name", "created_by", "created_at")
    search_fields = ("name",)
    readonly_fields = ("created_by", "created_at")

    def save_model(self, request, obj, form, change):
        if obj.created_by_id is None:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(SchoolClass)
class SchoolClassAdmin(admin.ModelAdmin):
    list_display = ("name", "subject", "school", "active_student_count")
    list_filter = ("school",)
    search_fields = ("name", "subject")
    inlines = [ClassMembershipInline]


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ("display_name", "school_class", "access_code", "is_active")
    list_filter = ("is_active", "school_class")
    search_fields = ("display_name", "access_code")
    readonly_fields = ("access_code",)
