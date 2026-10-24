from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils import timezone
from django.utils.html import format_html

from .models import TeacherAccessRequest, TeacherInvitation, User
from .services import build_invitation_url, send_invitation_email


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ("email",)
    list_display = ("email", "first_name", "last_name", "school", "is_staff")
    list_filter = ("is_staff", "is_superuser", "is_active", "school")
    search_fields = ("email", "first_name", "last_name")

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Persönliche Angaben", {"fields": ("first_name", "last_name", "school")}),
        (
            "Berechtigungen",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("Wichtige Daten", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "first_name",
                    "last_name",
                    "school",
                    "password1",
                    "password2",
                ),
            },
        ),
    )


def _invite_link_html(invitation, request):
    url = build_invitation_url(invitation, request)
    return format_html('<a href="{0}" target="_blank">{0}</a>', url)


@admin.register(TeacherInvitation)
class TeacherInvitationAdmin(admin.ModelAdmin):
    list_display = ("email", "school", "status_label", "created_at", "expires_at")
    list_filter = ("school",)
    search_fields = ("email", "first_name", "last_name")
    autocomplete_fields = ("school",)
    readonly_fields = ("token", "invite_link", "created_by", "accepted_at", "created_at")
    fields = (
        "email",
        "school",
        "first_name",
        "last_name",
        "expires_at",
        "invite_link",
        "token",
        "created_by",
        "accepted_at",
        "created_at",
    )

    @admin.display(description="Status")
    def status_label(self, obj):
        if obj.is_accepted:
            return "angenommen"
        if obj.is_expired:
            return "abgelaufen"
        return "offen"

    @admin.display(description="Einladungslink")
    def invite_link(self, obj):
        if not obj.pk:
            return "Wird nach dem Speichern angezeigt."
        return _invite_link_html(obj, getattr(self, "_request", None))

    def get_form(self, request, obj=None, **kwargs):
        # Stash the request so invite_link can build an absolute URL.
        self._request = request
        return super().get_form(request, obj, **kwargs)

    def save_model(self, request, obj, form, change):
        is_new = obj.pk is None
        if is_new and obj.created_by_id is None:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
        if is_new:
            url = build_invitation_url(obj, request)
            send_invitation_email(obj, url)
            self.message_user(
                request,
                format_html(
                    "Einladung erstellt. Link zum Weitergeben: {}",
                    _invite_link_html(obj, request),
                ),
            )


@admin.register(TeacherAccessRequest)
class TeacherAccessRequestAdmin(admin.ModelAdmin):
    list_display = ("full_name", "email", "school", "status", "created_at")
    list_filter = ("status", "school")
    search_fields = ("first_name", "last_name", "email")
    readonly_fields = ("created_at", "processed_at", "invitation")
    actions = ["approve_requests", "reject_requests"]

    @admin.display(description="Name")
    def full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}"

    @admin.action(description="Ausgewählte Anfragen genehmigen (Einladung erstellen)")
    def approve_requests(self, request, queryset):
        approved = 0
        for req in queryset.filter(status=TeacherAccessRequest.Status.PENDING):
            invitation = TeacherInvitation.objects.create(
                email=req.email,
                school=req.school,
                first_name=req.first_name,
                last_name=req.last_name,
                created_by=request.user,
            )
            req.status = TeacherAccessRequest.Status.APPROVED
            req.invitation = invitation
            req.processed_at = timezone.now()
            req.save(update_fields=["status", "invitation", "processed_at"])

            url = build_invitation_url(invitation, request)
            send_invitation_email(invitation, url)
            self.message_user(
                request,
                format_html(
                    "Genehmigt: {} – Einladungslink: {}",
                    req.email,
                    _invite_link_html(invitation, request),
                ),
            )
            approved += 1
        if not approved:
            self.message_user(request, "Keine offenen Anfragen ausgewählt.")

    @admin.action(description="Ausgewählte Anfragen ablehnen")
    def reject_requests(self, request, queryset):
        updated = queryset.filter(
            status=TeacherAccessRequest.Status.PENDING
        ).update(
            status=TeacherAccessRequest.Status.REJECTED,
            processed_at=timezone.now(),
        )
        self.message_user(request, f"{updated} Anfrage(n) abgelehnt.")
