from google import genai
from django.conf import settings

from .models import Document
from .vector_store import search_document_chunks


client = genai.Client(
    api_key=settings.GEMINI_API_KEY
)


def generate_rag_answer(question, owner_id, n_results=5):
    """
    Retrieve relevant document chunks and generate an answer using Gemini.

    Returns:
        {
            "answer": str,
            "sources": list
        }
    """

    # 1. Retrieve relevant chunks from ChromaDB
    results = search_document_chunks(
        question,
        owner_id=owner_id,
        n_results=n_results,
    )

    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]

    # 2. Handle case where no relevant chunks are found
    if not documents:
        return {
            "answer": "I couldn't find any relevant information in your documents.",
            "sources": [],
        }

    # 3. Combine retrieved chunks into context
    context = "\n\n---\n\n".join(documents)

    # 4. Build the RAG prompt
    prompt = f"""
You are an AI tutor.

Answer the student's question using the provided context.

Rules:
- Use the provided context as the primary source of information.
- Do not invent facts.
- If the answer cannot be found in the context, say that the
  information is not available in the provided documents.
- Explain the answer clearly and simply.
- Use bullet points when useful.

Context:
{context}

Student Question:
{question}
"""

    # 5. Generate the answer using Gemini
    interaction = client.interactions.create(
        model="gemini-3.6-flash",
        input=prompt,
    )

    answer = interaction.output_text

    # 6. Get document IDs from retrieved metadata
    document_ids = {
        int(metadata["document_id"])
        for metadata in metadatas
    }

    # 7. Get document titles from Django
    document_titles = dict(
        Document.objects.filter(
            id__in=document_ids,
            owner_id=owner_id,
        ).values_list(
            "id",
            "title",
        )
    )

    # 8. Build readable source information
    sources = []

    for metadata in metadatas:
        document_id = int(metadata["document_id"])

        sources.append(
            {
                "document_id": document_id,
                "document_title": document_titles.get(
                    document_id,
                    "Unknown document",
                ),
                "chunk_index": metadata["chunk_index"],
            }
        )

    # 9. Return answer + sources
    return {
        "answer": answer,
        "sources": sources,
    }

