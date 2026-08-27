from google import genai
from django.conf import settings


client = genai.Client(
    api_key=settings.GEMINI_API_KEY
)


def generate_embedding(text):
    """
    Generate an embedding vector for document text.
    """

    result = client.models.embed_content(
        model="gemini-embedding-001",
        contents=text,
    )

    return result.embeddings[0].values