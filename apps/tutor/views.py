from groq import Groq
from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views import View
from django.utils.decorators import method_decorator
from .models import TutorSession, ChatMessage
from apps.documents.models import Document


def call_groq_api(api_key, user_message, history_messages=None):
    """
    Official Groq SDK caller with dynamic active model discovery.
    """
    system_prompt = (
        "You are Tutor, an elite, encouraging, and highly knowledgeable AI Academic Tutor for college students. "
        "Provide direct, well-structured explanations using markdown bullet points and syntax-highlighted code blocks where helpful. "
        "Never output internal thinking or <think> tags. Always reply directly, clearly, and warmly to the student."
    )

    messages = [{"role": "system", "content": system_prompt}]

    if history_messages:
        for msg in history_messages:
            role = "user" if msg.role == "user" else "assistant"
            messages.append({"role": role, "content": msg.content})

    messages.append({"role": "user", "content": user_message})

    client = Groq(api_key=api_key)

    candidate_models = []
    try:
        models_data = client.models.list().data
        candidate_models = [
            m.id for m in models_data
            if not any(x in m.id.lower() for x in ['whisper', 'embed', 'guard', 'vision'])
        ]
        candidate_models.sort(
            key=lambda name: (
                0 if '3.3-70b' in name else
                1 if '70b' in name else
                2 if '8b' in name else
                3
            )
        )
    except Exception as list_err:
        print(f"[Groq ListModels Note]: {list_err}")
        candidate_models = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]

    last_error = ""

    for model_name in candidate_models:
        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=messages,
                temperature=0.6,
                max_tokens=1200,
            )
            reply_text = response.choices[0].message.content.strip()

            if "<think>" in reply_text and "</think>" in reply_text:
                reply_text = reply_text.split("</think>")[-1].strip()

            return reply_text

        except Exception as e:
            last_error = str(e)
            continue

    return f"⚠️ **Tutor AI Note**: Could not reach Groq. Details: {last_error}"


@method_decorator(login_required, name='dispatch')
class DashboardView(View):
    def get(self, request):
        # Fetch live database counts for the student
        total_docs = Document.objects.filter(owner=request.user).count()
        chat_sessions = TutorSession.objects.filter(user=request.user).count()
        total_quizzes = 0

        context = {
            'total_docs': total_docs,
            'total_quizzes': total_quizzes,
            'chat_sessions': chat_sessions,
        }
        return render(request, 'tutor/dashboard.html', context)


@method_decorator(login_required, name='dispatch')
class TutorChatView(View):
    def get(self, request, session_id=None):
        all_sessions = TutorSession.objects.filter(user=request.user)

        if session_id:
            active_session = get_object_or_404(TutorSession, id=session_id, user=request.user)
        else:
            active_session = all_sessions.first()
            if not active_session:
                active_session = TutorSession.objects.create(user=request.user, title="First Study Session")

        active_session.messages.filter(content__icontains="⚠️").delete()
        active_session.messages.filter(content__icontains="Error communicating").delete()

        messages = active_session.messages.all()
        return render(request, 'tutor/chat.html', {
            'active_session': active_session,
            'chat_messages': messages,
            'past_sessions': all_sessions,
        })

    def post(self, request, session_id=None):
        user_message = request.POST.get('message', '').strip()
        if not user_message:
            return JsonResponse({'error': 'Message cannot be empty'}, status=400)

        if session_id:
            session = get_object_or_404(TutorSession, id=session_id, user=request.user)
        else:
            session = TutorSession.objects.filter(user=request.user).first()
            if not session:
                session = TutorSession.objects.create(user=request.user, title="New Study Session")

        ChatMessage.objects.create(session=session, role='user', content=user_message)

        api_key = getattr(settings, 'GROQ_API_KEY', '')
        if not api_key or 'your_actual' in api_key:
            reply = "⚠️ **Missing Groq API Key**: Please configure `GROQ_API_KEY=gsk_...` in your `.env` file."
            return JsonResponse({'reply': reply})

        default_titles = ["New Study Session", "First Study Session", "New Chat"]
        if session.title in default_titles:
            summary_title = user_message[:25].capitalize() + ("..." if len(user_message) > 25 else "")
            session.title = summary_title
            session.save()

        past_messages = list(session.messages.exclude(content__icontains="⚠️").order_by('timestamp'))[-8:]

        ai_reply = call_groq_api(api_key, user_message, past_messages)

        if not ai_reply.startswith("⚠️"):
            ChatMessage.objects.create(session=session, role='model', content=ai_reply)

        return JsonResponse({
            'reply': ai_reply,
            'session_title': session.title,
            'session_id': session.id
        })


@method_decorator(login_required, name='dispatch')
class NewSessionView(View):
    def get(self, request):
        new_session = TutorSession.objects.create(user=request.user, title="New Chat")
        return redirect('tutor_chat_session', session_id=new_session.id)


@method_decorator(login_required, name='dispatch')
class ClearSessionView(View):
    def post(self, request, session_id):
        session = get_object_or_404(TutorSession, id=session_id, user=request.user)
        session.messages.all().delete()
        session.title = "New Chat"
        session.save()
        return JsonResponse({'success': True})


@method_decorator(login_required, name='dispatch')
class QuizzesView(View):
    def get(self, request):
        return render(request, 'tutor/quizzes.html')