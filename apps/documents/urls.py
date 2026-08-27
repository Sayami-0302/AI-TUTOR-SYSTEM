from django.urls import path
from .views import DocumentUploadView, DocumentListView

app_name = "documents"

urlpatterns = [
    path("", DocumentListView.as_view(), name="list"),
    path("upload/", DocumentUploadView.as_view(), name="upload"),
]