from django.urls import path

from .views import DocumentUploadView,DocumentListView

app_name = "documents"

urlpatterns = [
    path(
        "upload/",
        DocumentUploadView.as_view(),
        name="upload",
    ),
    path(
        "",
        DocumentListView.as_view(),
        name="list",
    ),
]