from django.contrib import admin

from .models import Document


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "owner",
        "status",
        "uploaded_at",
    )

    list_filter = (
        "status",
        "uploaded_at",
    )

    search_fields = (
        "title",
        "owner__username",
        "owner__email",
    )