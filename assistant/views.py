
import hashlib
import os

from django.conf import settings
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from pypdf import PdfReader
from .models import Document, ChatMessage
from .rag import (
    save_chunks,
    delete_document_chunks,
    generate_answer,
)


def split_into_chunks(text, chunk_size=500):
    words = text.split()
    chunks = []

    for i in range(0, len(words), chunk_size):
        chunk = " ".join(words[i:i + chunk_size])

        if chunk.strip():
            chunks.append(chunk)

    return chunks


def process_pdf(document):
    """
    Extract page-wise chunks and index them in ChromaDB.
    """

    reader = PdfReader(document.file.path)

    chunks = []
    metadatas = []

    for page_number, page in enumerate(reader.pages, start=1):
        page_text = page.extract_text() or ""

        if not page_text.strip():
            continue

        page_chunks = split_into_chunks(page_text)

        for chunk in page_chunks:
            chunks.append(chunk)
            metadatas.append({
                "source": document.title,
                "page": page_number,
                "document_id": str(document.pk),
                "file_hash": document.file_hash,
            })

    if not chunks:
        raise ValueError(
            "PDF se readable text nahi mila. "
            "Text-based PDF upload karein."
        )

    saved_count = save_chunks(chunks, metadatas)

    document.chunk_count = saved_count
    document.status = "indexed"
    document.save(update_fields=["chunk_count", "status"])

    return saved_count


def home(request):
    return render(request, "assistant/home.html")


def upload_pdf(request):
    if request.method == "POST":
        pdf_file = request.FILES.get("pdf_file")

        if not pdf_file:
            messages.error(request, "Please select a PDF file.")
            return redirect("upload_pdf")

        if not pdf_file.name.lower().endswith(".pdf"):
            messages.error(request, "Only PDF files are supported.")
            return redirect("upload_pdf")

        # Read bytes to calculate a content-based duplicate hash.
        file_bytes = pdf_file.read()
        file_hash = hashlib.sha256(file_bytes).hexdigest()
        pdf_file.seek(0)

        existing = Document.objects.filter(
            file_hash=file_hash
        ).first()

        if existing:
            messages.warning(
                request,
                f"Duplicate PDF: '{existing.title}' already exists."
            )
            return redirect("document_list")

        document = Document(
            title=os.path.basename(pdf_file.name),
            file_hash=file_hash,
            status="pending",
        )

        try:
            document.file.save(
                os.path.basename(pdf_file.name),
                pdf_file,
                save=True,
            )

            process_pdf(document)

            messages.success(
                request,
                f"'{document.title}' uploaded and indexed successfully."
            )

        except Exception as error:
            print("PDF upload/index error:", str(error))

            # Clean up the incomplete record and stored file.
            if document.pk:
                if document.file:
                    document.file.delete(save=False)

                document.delete()

            messages.error(
                request,
                "PDF process nahi ho saka. "
                "Please terminal mein error check karein."
            )

        return redirect("document_list")

    return render(request, "assistant/upload.html")


def document_list(request):
    documents = Document.objects.order_by("-uploaded_at")

    return render(
        request,
        "assistant/document_list.html",
        {"documents": documents},
    )


def delete_pdf(request, pk):
    if request.method != "POST":
        messages.error(request, "Please use the delete form.")
        return redirect("document_list")

    document = get_object_or_404(Document, pk=pk)

    try:
        delete_document_chunks(document.pk)

        if document.file:
            document.file.delete(save=False)

        title = document.title
        document.delete()

        messages.success(
            request,
            f"'{title}' deleted successfully."
        )

    except Exception as error:
        print("Document delete error:", str(error))
        messages.error(
            request,
            "Document delete nahi ho saka. Terminal check karein."
        )

    return redirect("document_list")


def reindex_pdf(request, pk):
    if request.method != "POST":
        messages.error(request, "Please use the re-index form.")
        return redirect("document_list")

    document = get_object_or_404(Document, pk=pk)

    try:
        # Remove the old indexed chunks before rebuilding.
        delete_document_chunks(document.pk)

        document.status = "pending"
        document.chunk_count = 0
        document.save(update_fields=["status", "chunk_count"])

        process_pdf(document)

        messages.success(
            request,
            f"'{document.title}' re-indexed successfully."
        )

    except Exception as error:
        print("Re-index error:", str(error))

        document.status = "failed"
        document.chunk_count = 0
        document.save(update_fields=["status", "chunk_count"])

        messages.error(
            request,
            "Re-index nahi ho saka. Original PDF retained hai; "
            "terminal mein error check karein."
        )

    return redirect("document_list")



def chat(request):
    answer = ""
    question = ""

    if request.method == "POST":
        question = request.POST.get("question", "").strip()

        if question:
            try:
                answer = generate_answer(question)

                ChatMessage.objects.create(
                    question=question,
                    answer=answer,
                )

            except Exception as error:
                print("Chat error:", str(error))
                answer = (
                    "Answer generate nahi ho saka. "
                    "Django terminal mein error check karein."
                )
        else:
            answer = "Please enter a question."

    history = ChatMessage.objects.order_by("-created_at")[:20]

    return render(
        request,
        "assistant/chat.html",
        {
            "question": question,
            "answer": answer,
            "history": history,
        },
    )
    answer = ""
    question = ""

    if request.method == "POST":
        question = request.POST.get("question", "").strip()

        if question:
            answer = generate_answer(question)
        else:
            answer = "Please enter a question."

    return render(
        request,
        "assistant/chat.html",
        {
            "question": question,
            "answer": answer,
        },
    )
