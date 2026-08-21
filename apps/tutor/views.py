import os
import google.generativeai as genai
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views import View
from django.utils.decorators import method_decorator
from .models import TutorSession, ChatMessage

# Configure Gemini API
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

@method_decorator(login_required, name='dispatch')
class DashboardView(View):
    def get(self, request):
        # Dynamically calculate metric counts for current user
        total_docs = 0  # Hook up to documents later
        total_quizzes = 0  # Hook up to quizzes later
        chat_sessions = TutorSession.objects.filter(user=request.user).count()

        context = {
            'total_docs': total_docs,
            'total_quizzes': total_quizzes,
            'chat_sessions': chat_sessions,
        }
        return render(request, 'tutor/dashboard.html', context)

@method_decorator(login_required, name='dispatch')
class TutorChatView(View):
    def get(self, request):
        # Get or create the most recent active session for this user
        session, created = TutorSession.objects.get_or_create(user=request.user)
        # Retrieve all previous chat messages for this session
        messages = session.messages.all()
        return render(request, 'tutor/chat.html', {
            'session': session,
            'chat_messages': messages
        })

    def post(self, request):
        """API Endpoint to handle sending messages to Gemini"""
        user_message = request.POST.get('message', '').strip()
        if not user_message:
            return JsonResponse({'error': 'Message cannot be empty'}, status=400)

        # Retrieve the user's active session
        session = get_object_or_404(TutorSession, user=request.user)

        # 1. Save User Message to Database
        ChatMessage.objects.create(session=session, role='user', content=user_message)

        # 2. Compile Chat History for Gemini's Memory Context
        history = []
        # Let's give Gemini a strong System Instruction so it acts like a professional college tutor
        system_instruction = (
            "You are an elite, encouraging, and highly knowledgeable AI academic tutor. "
            "Your goal is to help college students master engineering, programming, mathematics, and science. "
            "Explain concepts simply, use clean formatting, markdown list points, and write code blocks with syntax styling where needed. "
            "Never write answers that are too lengthy; be concise and prompt the student to ask follow-up questions."
        )

        # Build message history array
        for msg in session.messages.all():
            history.append({
                "role": "user" if msg.role == "user" else "model",
                "parts": [msg.content]
            })

        try:
            # 3. Call the Gemini API
            model = genai.GenerativeModel(
                model_name="gemini-1.5-flash",
                system_instruction=system_instruction
            )
            chat = model.start_chat(history=history[:-1]) # Don't pass the latest duplicate message
            response = chat.send_message(user_message)
            ai_reply = response.text

            # 4. Save AI Response to Database
            ChatMessage.objects.create(session=session, role='model', content=ai_reply)

            return JsonResponse({
                'reply': ai_reply
            })

        except Exception as e:
            # Fallback reply in case API keys are missing or invalid
            error_msg = f"Tutor System Note: Gemini API call failed. Exception: {str(e)}"
            return JsonResponse({
                'reply': "I am having trouble connecting to my cognitive networks. Please make sure the 'GEMINI_API_KEY' is correctly configured inside your .env file."
            })

@method_decorator(login_required, name='dispatch')
class DocumentsView(View):
    def get(self, request):
        return render(request, 'tutor/documents.html')

@method_decorator(login_required, name='dispatch')
class QuizzesView(View):
    def get(self, request):
        return render(request, 'tutor/quizzes.html')