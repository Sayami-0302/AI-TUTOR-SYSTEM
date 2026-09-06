from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .rag import generate_rag_answer


class TutorAskView(APIView):
    """
    API endpoint for asking questions to the AI tutor.

    Requires the user to be authenticated using
    the existing Django session.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        # Debug: see exactly what the API receives
        print("REQUEST DATA:", request.data)

        question = request.data.get("question", "").strip()

        # Debug: see the extracted question
        print("QUESTION:", repr(question))

        # Validate question
        if not question:
            return Response(
                {
                    "error": "Question is required."
                },
                status=400,
            )

        # Generate RAG answer
        result = generate_rag_answer(
            question=question,
            owner_id=request.user.id,
        )

        # Return answer and sources
        return Response(
            {
                "question": question,
                "answer": result["answer"],
                "sources": result["sources"],
            }
        )