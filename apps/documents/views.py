from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect, render
from django.views import View
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
                {"error": "Please select a file."},
            )

        try:
            create_document(
                user=request.user,
                file=uploaded_file,
            )
        except Exception as e:
            return render(
                request,
                "documents/upload.html",
                {"error": str(e)},
            )

        return redirect("documents:list")



class DocumentListView(LoginRequiredMixin, View):

    def get(self, request):
        documents = Document.objects.filter(
            owner=request.user
        ).order_by("-uploaded_at")

        return render(
            request,
            "documents/list.html",
            {"documents": documents},
        )

    