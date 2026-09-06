import os
from django.conf import settings
from .models import Document
from .vector_store import search_document_chunks

# Safe import of google-genai
try:
    from google import genai
    gemini_available = True
except ImportError:
    gemini_available = False

# Safe import of Groq
try:
    from groq import Groq
    groq_available = True
except ImportError:
    groq_available = False


def generate_rag_answer(question, owner_id, n_results=5):
    """
    Retrieves relevant document chunks from ChromaDB and generates
    an accurate, cited answer using AI with full source attribution.

    Returns:
        {
            "answer": str,
            "sources": list of dicts [{"document_id", "document_title", "chunk_index"}]
        }
    """
    if not question or not str(question).strip():
        return {
            "answer": "Please provide a question to search your documents.",
            "sources": []
        }

    # 1. Retrieve relevant chunks from ChromaDB
    try:
        results = search_document_chunks(
            query=question,
            owner_id=owner_id,
            n_results=n_results,
        )
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
    except Exception as search_err:
        print(f"[ChromaDB Search Note]: {search_err}")
        documents = []
        metadatas = []

    # 2. Handle case where no relevant chunks are found
    if not documents:
        return {
            "answer": "I couldn't find any relevant information in your uploaded documents. Make sure you have uploaded the relevant study notes in your Document Library.",
            "sources": [],
        }

    # 3. Combine retrieved chunks into clean context
    context = "\n\n---\n\n".join(documents)

    # 4. Build prompt
    prompt = f"""You are an elite AI Academic Tutor.

Answer the student's question strictly using the provided context from their uploaded notes.

Rules:
- Use the provided context as your primary source of truth.
- Do not invent facts or hallucinate details not present in the notes.
- If the exact answer is not in the context, state clearly what is covered and what is missing.
- Format your response cleanly using markdown bullet points and code blocks where helpful.

Context from Student Notes:
---
{context}
---

Student Question:
{question}
"""

    answer_text = None

    # 5. Try Groq first for sub-second speed if available
    groq_key = getattr(settings, 'GROQ_API_KEY', '') or os.getenv('GROQ_API_KEY', '')
    if groq_available and groq_key:
        try:
            client = Groq(api_key=groq_key)
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": "You are a precise academic tutor answering strictly from student notes."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                max_tokens=1200
            )
            answer_text = response.choices[0].message.content.strip()
        except Exception as groq_err:
            print(f"[RAG Groq fallback note]: {groq_err}")

    # 6. Try Gemini as fallback if Groq was unavailable or failed
    if not answer_text and gemini_available:
        gemini_key = getattr(settings, 'GEMINI_API_KEY', '') or os.getenv('GEMINI_API_KEY', '')
        if gemini_key:
            try:
                g_client = genai.Client(api_key=gemini_key)
                # Try active gemini models
                for g_model in ["gemini-2.0-flash", "gemini-1.5-flash"]:
                    try:
                        response = g_client.models.generate_content(
                            model=g_model,
                            contents=prompt
                        )
                        if response and response.text:
                            answer_text = response.text.strip()
                            break
                    except Exception:
                        continue
            except Exception as g_err:
                print(f"[RAG Gemini error]: {g_err}")

    if not answer_text:
        answer_text = (
            "I found matching passages in your documents, but the AI generation service is temporarily unavailable. "
            "Please verify your `GROQ_API_KEY` or `GEMINI_API_KEY` in `.env`."
        )

    # 7. Extract document IDs and fetch actual titles from Django DB
    document_ids = set()
    for meta in metadatas:
        if isinstance(meta, dict) and "document_id" in meta:
            try:
                document_ids.add(int(meta["document_id"]))
            except (ValueError, TypeError):
                continue

    document_titles = dict(
        Document.objects.filter(
            id__in=document_ids,
            owner_id=owner_id,
        ).values_list("id", "title")
    )

    # 8. Build readable source attribution list
    sources = []
    seen_sources = set()

    for meta in metadatas:
        if not isinstance(meta, dict):
            continue
        try:
            doc_id = int(meta.get("document_id", 0))
            chunk_idx = meta.get("chunk_index", 0)
            doc_title = document_titles.get(doc_id, "Uploaded Document")

            source_key = (doc_id, chunk_idx)
            if source_key not in seen_sources:
                seen_sources.add(source_key)
                sources.append({
                    "document_id": doc_id,
                    "document_title": doc_title,
                    "chunk_index": chunk_idx,
                })
        except Exception:
            continue

    # 9. Return structured answer with cited sources
    return {
        "answer": answer_text,
        "sources": sources,
    }