from django.contrib import admin

from .models import MaterialFile, MaterialFolder


@admin.register(MaterialFolder)
class MaterialFolderAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "parent", "created_at")
    search_fields = ("name", "owner__email")


@admin.register(MaterialFile)
class MaterialFileAdmin(admin.ModelAdmin):
    list_display = ("original_name", "owner", "folder", "size", "created_at")
    search_fields = ("original_name", "owner__email")
