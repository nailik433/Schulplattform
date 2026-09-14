from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView

from schools.views import home

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", home, name="home"),
    path(
        "impressum/",
        TemplateView.as_view(template_name="legal/impressum.html"),
        name="impressum",
    ),
    path(
        "datenschutz/",
        TemplateView.as_view(template_name="legal/datenschutz.html"),
        name="datenschutz",
    ),
    path("konto/", include("accounts.urls")),
    path("", include("worksheets.urls")),
    path("", include("schools.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.BASE_DIR / "static")
