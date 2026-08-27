import os
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect, render, get_object_or_404
from django.views import View
from django.contrib import messages
from django.db.models import Q
from .models import Document
from .services import create_document


class DocumentUploadView(LoginRequiredMixin, View):
    def get(self, request):
        return render(request, "documents/upload.html")

    def post(self, request):
        uploaded_file = request.FILES.get("file")

        if not uploaded_file:
            return render(
                request,
                "documents/upload.html",
                {"error": "Please select a file to upload."},
            )

        try:
            document = create_document(
                user=request.user,
                file=uploaded_file,
            )
            messages.success(request, f"Document '{document.title}' uploaded and processed successfully!")
            return redirect("documents:list")
        except Exception as e:
            return render(
                request,
                "documents/upload.html",
                {"error": f"Upload processing error: {str(e)}"},
            )


class DocumentListView(LoginRequiredMixin, View):
    def get(self, request):
        query = request.GET.get('q', '').strip()
        documents = Document.objects.filter(owner=request.user).order_by("-uploaded_at")

        if query:
            documents = documents.filter(
                Q(title__icontains=query) | Q(file__icontains=query)
            )

        return render(
            request,
            "documents/list.html",
            {
                "documents": documents,
                "query": query,
                "total_docs": documents.count()
            },
        )


class DocumentDeleteView(LoginRequiredMixin, View):
    def post(self, request, doc_id):
        document = get_object_or_404(Document, id=doc_id, owner=request.user)
        title = document.title

        # Safely remove physical file from disk
        if document.file:
            try:
                if os.path.isfile(document.file.path):
                    os.remove(document.file.path)
            except Exception as file_err:
                print(f"[File Removal Note]: {file_err}")

        # Delete database record (cascades to chunks & content)
        document.delete()
        messages.success(request, f"Document '{title}' was deleted successfully.")
        return redirect("documents:list")