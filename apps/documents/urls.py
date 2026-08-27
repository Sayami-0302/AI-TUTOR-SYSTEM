from django.urls import path
from .views import DocumentUploadView, DocumentListView, DocumentDeleteView

app_name = "documents"

urlpatterns = [
    path("", DocumentListView.as_view(), name="list"),
    path("upload/", DocumentUploadView.as_view(), name="upload"),
    path("delete/<int:doc_id>/", DocumentDeleteView.as_view(), name="delete"),
]