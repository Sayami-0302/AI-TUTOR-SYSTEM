from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views import View
from django.utils.decorators import method_decorator

from .models import TutorSession, ChatMessage
from apps.documents.models import Document
from apps.documents.rag import generate_rag_answer


@method_decorator(login_required, name="dispatch")
class DashboardView(View):
    def get(self, request):
        # Fetch live database counts for the student
        total_docs = Document.objects.filter(
            owner=request.user
        ).count()

        chat_sessions = TutorSession.objects.filter(
            user=request.user
        ).count()

        total_quizzes = 0

        context = {
            "total_docs": total_docs,
            "total_quizzes": total_quizzes,
            "chat_sessions": chat_sessions,
        }

        return render(
            request,
            "tutor/dashboard.html",
            context
        )


@method_decorator(login_required, name="dispatch")
class TutorChatView(View):

    def get(self, request, session_id=None):

        all_sessions = TutorSession.objects.filter(
            user=request.user
        )

        if session_id:
            active_session = get_object_or_404(
                TutorSession,
                id=session_id,
                user=request.user
            )
        else:
            active_session = all_sessions.first()

            if not active_session:
                active_session = TutorSession.objects.create(
                    user=request.user,
                    title="First Study Session"
                )

        # Remove old error messages from the chat
        active_session.messages.filter(
            content__icontains="⚠️"
        ).delete()

        active_session.messages.filter(
            content__icontains="Error communicating"
        ).delete()

        messages = active_session.messages.all()

        return render(
            request,
            "tutor/chat.html",
            {
                "active_session": active_session,
                "chat_messages": messages,
                "past_sessions": all_sessions,
            }
        )

    def post(self, request, session_id=None):

        # ---------------------------------------------------------
        # 1. Get user question
        # ---------------------------------------------------------

        user_message = request.POST.get(
            "message",
            ""
        ).strip()

        if not user_message:
            return JsonResponse(
                {
                    "error": "Message cannot be empty"
                },
                status=400
            )

        # ---------------------------------------------------------
        # 2. Get / create chat session
        # ---------------------------------------------------------

        if session_id:

            session = get_object_or_404(
                TutorSession,
                id=session_id,
                user=request.user
            )

        else:

            session = TutorSession.objects.filter(
                user=request.user
            ).first()

            if not session:
                session = TutorSession.objects.create(
                    user=request.user,
                    title="New Study Session"
                )

        # ---------------------------------------------------------
        # 3. Save user's message
        # ---------------------------------------------------------

        ChatMessage.objects.create(
            session=session,
            role="user",
            content=user_message
        )

        # ---------------------------------------------------------
        # 4. Rename new/default session
        # ---------------------------------------------------------

        default_titles = [
            "New Study Session",
            "First Study Session",
            "New Chat",
        ]

        if session.title in default_titles:

            summary_title = (
                user_message[:25].capitalize()
                + ("..." if len(user_message) > 25 else "")
            )

            session.title = summary_title
            session.save(
                update_fields=["title"]
            )

        # ---------------------------------------------------------
        # 5. Generate RAG answer
        # ---------------------------------------------------------

        try:

            result = generate_rag_answer(
                question=user_message,
                owner_id=request.user.id,
                n_results=5,
            )

            ai_reply = result["answer"]
            sources = result["sources"]

        except Exception as e:

            print(
                f"[RAG ERROR] {type(e).__name__}: {e}"
            )

            return JsonResponse(
                {
                    "error": "The tutor could not generate a response.",
                    "reply": (
                        "⚠️ **Tutor Error**: "
                        "Something went wrong while generating the answer."
                    ),
                    "session_title": session.title,
                    "session_id": session.id,
                    "sources": [],
                },
                status=500
            )

        # ---------------------------------------------------------
        # 6. Save AI response
        # ---------------------------------------------------------

        if ai_reply:

            ChatMessage.objects.create(
                session=session,
                role="model",
                content=ai_reply
            )

        # ---------------------------------------------------------
        # 7. Return response to frontend
        # ---------------------------------------------------------

        return JsonResponse(
            {
                "reply": ai_reply,
                "sources": sources,
                "session_title": session.title,
                "session_id": session.id,
            }
        )


@method_decorator(login_required, name="dispatch")
class NewSessionView(View):

    def get(self, request):

        new_session = TutorSession.objects.create(
            user=request.user,
            title="New Chat"
        )

        return redirect(
            "tutor_chat_session",
            session_id=new_session.id
        )


@method_decorator(login_required, name="dispatch")
class ClearSessionView(View):

    def post(self, request, session_id):

        session = get_object_or_404(
            TutorSession,
            id=session_id,
            user=request.user
        )

        session.messages.all().delete()

        session.title = "New Chat"

        session.save(
            update_fields=["title"]
        )

        return JsonResponse(
            {
                "success": True
            }
        )


@method_decorator(login_required, name="dispatch")
class QuizzesView(View):

    def get(self, request):

        return render(
            request,
            "tutor/quizzes.html"
        )