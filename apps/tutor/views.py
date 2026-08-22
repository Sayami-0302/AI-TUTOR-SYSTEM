import google.generativeai as genai
from django.conf import settings
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views import View
from django.utils.decorators import method_decorator
from .models import TutorSession, ChatMessage
from apps.documents.models import Document
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView

@method_decorator(login_required, name='dispatch')
class DashboardView(View):
    def get(self, request):
        chat_sessions = TutorSession.objects.filter(user=request.user).count()
        context = {
            'total_docs': 0,
            'total_quizzes': 0,
            'chat_sessions': chat_sessions,
        }
        return render(request, 'tutor/dashboard.html', context)


@method_decorator(login_required, name='dispatch')
class TutorChatView(View):
    def get(self, request):
        session, _ = TutorSession.objects.get_or_create(user=request.user)
        messages = session.messages.all()
        return render(request, 'tutor/chat.html', {
            'session': session,
            'chat_messages': messages
        })

    def post(self, request):
        user_message = request.POST.get('message', '').strip()
        if not user_message:
            return JsonResponse({'error': 'Message cannot be empty'}, status=400)

        session, _ = TutorSession.objects.get_or_create(user=request.user)

        # 1. Save User Message
        ChatMessage.objects.create(session=session, role='user', content=user_message)

        # 2. Check API Key
        api_key = getattr(settings, 'GEMINI_API_KEY', '')
        if not api_key or api_key == 'your_actual_gemini_api_key_here':
            reply = (
                "⚠️ Gemini API Key is missing or invalid. "
                "Please add a valid `GEMINI_API_KEY` to your `.env` file and restart the server."
            )
            ChatMessage.objects.create(session=session, role='model', content=reply)
            return JsonResponse({'reply': reply})

        try:
            # 3. Configure and Call Gemini
            genai.configure(api_key=api_key)

            system_instruction = (
                "You are an elite, encouraging, and highly knowledgeable AI Academic Tutor. "
                "Your goal is to help college students master engineering, computer science, mathematics, and academic coursework. "
                "Explain concepts clearly and concisely. Use markdown formatting with bullet points and code blocks with syntax highlighting where relevant. "
                "Encourage critical thinking and keep explanations focused."
            )

            # Build history for conversation context
            history = []
            for msg in session.messages.all():
                history.append({
                    "role": "user" if msg.role == "user" else "model",
                    "parts": [msg.content]
                })

            # Pass history excluding the message we just added
            model = genai.GenerativeModel(
                model_name="gemini-1.5-flash",
                system_instruction=system_instruction
            )
            chat = model.start_chat(history=history[:-1])
            response = chat.send_message(user_message)
            ai_reply = response.text

            # 4. Save AI Response
            ChatMessage.objects.create(session=session, role='model', content=ai_reply)

            return JsonResponse({'reply': ai_reply})

        except Exception as e:
            # Print exact error to PowerShell console for debugging
            print(f"\n[Gemini Error Details]: {e}\n")
            error_reply = f"Error communicating with Tutor AI: {str(e)}"
            ChatMessage.objects.create(session=session, role='model', content=error_reply)
            return JsonResponse({'reply': error_reply})


@method_decorator(login_required, name='dispatch')
class DocumentsView(LoginRequiredMixin, TemplateView):
    template_name = "tutor/documents.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["documents"] = Document.objects.filter(
            owner=self.request.user
        ).order_by("-uploaded_at")

        return context


@method_decorator(login_required, name='dispatch')
class QuizzesView(View):
    def get(self, request):
        return render(request, 'tutor/quizzes.html')