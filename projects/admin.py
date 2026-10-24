from django.contrib import admin

from .models import ClassProject, Project, ProjectItem


class ProjectItemInline(admin.TabularInline):
    model = ProjectItem
    extra = 0
    fields = ("kind", "position", "title")


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("title", "owner", "updated_at")
    inlines = [ProjectItemInline]


@admin.register(ClassProject)
class ClassProjectAdmin(admin.ModelAdmin):
    list_display = ("title", "school_class", "created_at")
