"""Root URL configuration."""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from users.views import HomeView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('tinymce/', include('tinymce.urls')),
    path('users/', include('users.urls')),
    path('accounts/', include('allauth.urls')),
    path('gcodex/', include('gcodex.urls')),
    path('itineraries/', include('itineraries.urls')),
    path('', HomeView.as_view(), name='home'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
