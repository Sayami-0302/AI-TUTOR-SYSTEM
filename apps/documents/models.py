from django.conf import settings
from django.db import models


class Document(models.Model):
    STATUS_CHOICES = [
        ("uploaded", "Uploaded"),
        ("processing", "Processing"),
        ("ready", "Ready"),
        ("failed", "Failed"),
    ]

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="documents",
    )

    title = models.CharField(max_length=255)

    file = models.FileField(upload_to="documents/")

    uploaded_at = models.DateTimeField(auto_now_add=True)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="uploaded",
    )

    def __str__(self):
        return self.title


class DocumentContent(models.Model):
    document = models.OneToOneField(
        Document,
        on_delete=models.CASCADE,
        related_name="content",
    )

    text = models.TextField()

    extracted_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Content - {self.document.title}"