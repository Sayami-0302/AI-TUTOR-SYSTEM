from .models import Document
from .validators import validate_pdf


def create_document(*, user, file):
    validate_pdf(file)

    document = Document.objects.create(
        owner=user,
        title=file.name,
        file=file,
        status="uploaded",
    )

    return document