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
    path('api/documents/', include('apps.documents.api_urls')),
    path('study/', include('apps.study.urls')),
    path('', lambda request: redirect('dashboard')),
]

# Serve uploaded PDF media files during local development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)