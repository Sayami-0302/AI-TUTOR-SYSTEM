import fitz
import re
from .models import Document, DocumentContent
from .validators import validate_pdf


def extract_pdf_text(file):
    text = []

    file.seek(0)

    with fitz.open(stream=file.read(), filetype="pdf") as pdf:
        for page in pdf:
            text.append(page.get_text())

    return "\n".join(text)



def clean_text(text):
    """
    Clean extracted PDF text while preserving meaningful content.
    """

    # Normalize line endings
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Replace tabs with spaces
    text = text.replace("\t", " ")

    # Remove excessive spaces
    text = re.sub(r"[ ]{2,}", " ", text)

    # Reduce excessive blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Remove spaces at the beginning/end of lines
    text = "\n".join(
        line.strip()
        for line in text.splitlines()
    )

    # Remove leading/trailing whitespace
    text = text.strip()

    return text

def create_document(*, user, file):
    validate_pdf(file)

    document = Document.objects.create(
        owner=user,
        title=file.name,
        file=file,
        status="processing",
    )

    try:
        extracted_text = extract_pdf_text(file)
        cleaned_text = clean_text(extracted_text)

        DocumentContent.objects.create(
            document=document,
            text=cleaned_text,
        )

        DocumentContent.objects.create(
            document=document,
            text=extracted_text,
        )

        document.status = "ready"
        document.save(update_fields=["status"])

    except Exception:
        document.status = "failed"
        document.save(update_fields=["status"])
        raise

    return document

