import chromadb
from pathlib import Path
from .embeddings import generate_embedding


BASE_DIR = Path(__file__).resolve().parent.parent.parent
CHROMA_PATH = BASE_DIR / "vector_store" / "chroma"


client = chromadb.PersistentClient(
    path=str(CHROMA_PATH)
)


collection = client.get_or_create_collection(
    name="document_chunks"
)




def add_document_chunks(document, chunks):
    """
    Generate embeddings and store document chunks in ChromaDB.
    """

    if not chunks:
        return

    ids = [
        f"document-{document.id}-chunk-{index}"
        for index in range(len(chunks))
    ]

    metadatas = [
        {
            "document_id": str(document.id),
            "owner_id": str(document.owner_id),
            "chunk_index": index,
        }
        for index in range(len(chunks))
    ]

    embeddings = [
        generate_embedding(chunk)
        for chunk in chunks
    ]

    collection.add(
        ids=ids,
        documents=chunks,
        embeddings=embeddings,
        metadatas=metadatas,
    )


def search_document_chunks(query, owner_id, n_results=5):
    """
    Search ChromaDB for chunks relevant to the user's query.
    Only searches documents belonging to the specified owner.
    """

    query_embedding = generate_embedding(query)

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=n_results,
        where={
            "owner_id": str(owner_id)
        },
    )

    return results