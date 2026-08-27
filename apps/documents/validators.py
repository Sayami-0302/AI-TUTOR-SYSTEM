from django.core.exceptions import ValidationError


MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


def validate_pdf(file):
    if not file:
        raise ValidationError("A file is required.")

    if not file.name.lower().endswith(".pdf"):
        raise ValidationError("Only PDF files are allowed.")

    if file.size > MAX_FILE_SIZE:
        raise ValidationError("File size must not exceed 10 MB.")