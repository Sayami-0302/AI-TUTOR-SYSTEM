from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.views import View
from django.utils.decorators import method_decorator

@method_decorator(login_required, name='dispatch')
class DashboardView(View):
    def get(self, request):
        # We can dynamically count stats from other tables here later
        context = {
            'total_docs': 3,       # Mock stats to display visual numbers
            'total_quizzes': 5,
            'chat_sessions': 12,
        }
        return render(request, 'tutor/dashboard.html', context)

@method_decorator(login_required, name='dispatch')
class TutorChatView(View):
    def get(self, request):
        return render(request, 'tutor/chat.html')