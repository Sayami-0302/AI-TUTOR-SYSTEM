import os
from django.conf import settings

# Lazy client storage
_genai_client = None


def get_genai_client():
    """
    Lazily initializes the Google GenAI client only when needed,
    preventing startup crashes when running migrations or tests.
    """
    global _genai_client
    if _genai_client is not None:
        return _genai_client

    api_key = getattr(settings, "GEMINI_API_KEY", "") or os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        raise ValueError(
            "GEMINI_API_KEY is not set in your .env file. "
            "Please configure GEMINI_API_KEY to generate document embeddings."
        )

    try:
        from google import genai
        _genai_client = genai.Client(api_key=api_key)
        return _genai_client
    except Exception as e:
        raise RuntimeError(f"Failed to initialize Google GenAI Client: {e}")


def generate_embedding(text):
    """
    Generates a vector embedding for a text chunk using Google's text-embedding-004 model.
    """
    if not text or not str(text).strip():
        return [0.0] * 768

    client = get_genai_client()

    try:
        response = client.models.embed_content(
            model="text-embedding-004",
            contents=text,
        )
        # Extract embedding vector
        if hasattr(response, 'embedding') and hasattr(response.embedding, 'values'):
            return response.embedding.values
        elif hasattr(response, 'embeddings') and len(response.embeddings) > 0:
            return response.embeddings[0].values
        elif isinstance(response, dict) and 'embedding' in response:
            return response['embedding']['values']
        else:
            # Fallback direct attribute access
            return list(response.embedding)
    except Exception as err:
        print(f"[Embedding Error]: {err}")
        # Return fallback zero-vector so process doesn't crash
        return [0.0] * 768