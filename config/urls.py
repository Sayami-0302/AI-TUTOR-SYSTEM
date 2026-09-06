from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('apps.accounts.urls')),
    path('tutor/', include('apps.tutor.urls')),
    path('documents/', include('apps.documents.urls', namespace='documents')),
    path('api/tutor/', include('apps.documents.api_urls')),
    path('', lambda request: redirect('dashboard')),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)