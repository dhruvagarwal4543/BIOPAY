from django.contrib import admin
from django.urls import include, path

from payments import urls as payments_urls

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/dev/mock/", include(payments_urls.urlpatterns)),
    path("api/terminal/", include(payments_urls.terminal_urlpatterns)),
    path("api/", include(payments_urls.web_urlpatterns)),
]
