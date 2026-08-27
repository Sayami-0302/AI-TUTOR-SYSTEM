import chromadb
from pathlib import Path


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
    Store document chunks in ChromaDB.
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

    collection.add(
        ids=ids,
        documents=chunks,
        metadatas=metadatas,
    )