
import os
import uuid

import chromadb
from groq import Groq


# ==========================================
# 1. CHROMADB CONFIGURATION
# ==========================================

BASE_DIR = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

CHROMA_PATH = os.path.join(BASE_DIR, "chroma_db")
COLLECTION_NAME = "company_documents"

chroma_client = chromadb.PersistentClient(
    path=CHROMA_PATH
)

collection = chroma_client.get_or_create_collection(
    name=COLLECTION_NAME
)


# ==========================================
# 2. SAVE PDF CHUNKS
# ==========================================

def save_chunks(chunks, metadatas=None):
    """
    Save document chunks and metadata into ChromaDB.
    Returns the number of saved chunks.
    """

    if not chunks:
        return 0

    if metadatas is None:
        metadatas = [{} for _ in chunks]

    if len(chunks) != len(metadatas):
        raise ValueError(
            "Chunks aur metadata ki count same honi chahiye."
        )

    valid_chunks = []
    valid_metadatas = []

    for chunk, metadata in zip(chunks, metadatas):
        if not isinstance(chunk, str) or not chunk.strip():
            continue

        clean_metadata = {}

        for key, value in metadata.items():
            if value is None:
                continue

            # ChromaDB metadata values must be supported scalar types.
            if isinstance(value, (str, int, float, bool)):
                clean_metadata[key] = value

        valid_chunks.append(chunk.strip())
        valid_metadatas.append(clean_metadata)

    if not valid_chunks:
        return 0

    ids = [
        f"chunk_{uuid.uuid4().hex}"
        for _ in valid_chunks
    ]

    collection.add(
        ids=ids,
        documents=valid_chunks,
        metadatas=valid_metadatas,
    )

    return len(valid_chunks)


# ==========================================
# 3. DELETE ONE DOCUMENT'S CHUNKS
# ==========================================

def delete_document_chunks(document_id):
    """
    Delete only the chunks associated with a document ID.
    """

    document_id = str(document_id)

    existing = collection.get(
        where={"document_id": document_id},
        include=["metadatas"],
    )

    ids = existing.get("ids", [])

    if ids:
        collection.delete(ids=ids)

    return len(ids)


# ==========================================
# 4. SEARCH RELEVANT DOCUMENT CHUNKS
# ==========================================

def search_chunks(question, n_results=3):
    """
    Search ChromaDB for chunks relevant to a question.
    Returns text, source, page, and distance.
    """

    question = question.strip()

    if not question:
        return []

    total_chunks = collection.count()

    if total_chunks == 0:
        return []

    n_results = max(1, min(n_results, total_chunks))

    results = collection.query(
        query_texts=[question],
        n_results=n_results,
        include=[
            "documents",
            "metadatas",
            "distances",
        ],
    )

    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    matched_chunks = []

    for index, text in enumerate(documents):
        metadata = (
            metadatas[index]
            if index < len(metadatas) and metadatas[index]
            else {}
        )

        distance = (
            distances[index]
            if index < len(distances)
            else None
        )

        matched_chunks.append({
            "text": text or "",
            "source": metadata.get(
                "source", "Unknown document"
            ),
            "page": metadata.get(
                "page", "Unknown"
            ),
            "document_id": metadata.get(
                "document_id", ""
            ),
            "distance": distance,
        })

    return matched_chunks


# ==========================================
# 5. GENERATE GROQ AI ANSWER
# ==========================================

def generate_answer(question):
    """
    Generate an answer using retrieved document context.
    The model is instructed not to invent missing information.
    """

    question = question.strip()

    if not question:
        return "Please enter a question."

        if detect_prompt_injection(question):
            print("Warning: Prompt injection detected in user question.")
            return("Security check: Your question contains suspicious "
                "instructions. Please ask a normal document-related question.")


    try:
        results = search_chunks(
            question,
            n_results=3,
        )

        if not results:
            return (
                "Uploaded documents mein searchable content nahi mila. "
                "Please pehle ek readable PDF upload aur index karein."
            )

        context_parts = []

        for item in results:
            text = item.get("text", "").strip()

            if not text:
                continue

            source = item.get(
                "source", "Unknown document"
            )
            page = item.get(
                "page", "Unknown"
            )

            context_parts.append(
                f"Source: {source}, Page: {page}\n{text}"
            )

        if not context_parts:
            return (
                "Relevant document content nahi mila. "
                "Please PDF indexing check karein."
            )

        context = "\n\n".join(context_parts)

        if detect_prompt_injection(context):
            print(
                "Warning: Suspicious instructions found "
                "in document context."
                )



        api_key = os.getenv("GROQ_API_KEY")

        if not api_key:
            return (
                "GROQ_API_KEY environment variable set nahi hai. "
                "Terminal mein API key configuration check karein."
            )

        client = Groq(api_key=api_key)

        response = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an Enterprise Document Assistant. "
                        "Answer using only the supplied document context. "
                        "Do not use outside knowledge or invent facts. "
                        "If the context does not contain enough information, "
                        "clearly state that the answer was not found in "
                        "the uploaded documents. "
                        "Give a clear, concise answer. "
                        "When supported by the context, mention the source "
                        "document and page number. "
                        "Do not claim a fact is in the document unless "
                        "the supplied context supports it."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Question:\n{question}\n\n"
                        f"Retrieved document context:\n{context}\n\n"
                        "Answer the question based only on this context."
                    ),
                },
            ],
            temperature=0,
        )

        answer = response.choices[0].message.content

        if not answer:
            return "AI se answer generate nahi ho saka."

        return answer.strip()

    except Exception as error:
        print("RAG answer error:", str(error))

        return (
            "Answer generate nahi ho saka. "
            "Django terminal mein error check karein."
        )


# ==========================================
# 6. DATABASE STATUS
# ==========================================

def get_database_status():
    """
    Return the current ChromaDB collection status.
    """

    return {
        "collection_name": COLLECTION_NAME,
        "database_path": CHROMA_PATH,
        "total_chunks": collection.count(),
    }
def detect_prompt_injection(text):
    suspicious_phrases = [
        "ignore all previous instructions",
        "ignore previous instructions",
        "reveal the system prompt",
        "reveal hidden instructions",
        "ignore all rules",
    ]

    text = text.lower()

    for phrase in suspicious_phrases:
        if phrase in text:
            return True

    return False

