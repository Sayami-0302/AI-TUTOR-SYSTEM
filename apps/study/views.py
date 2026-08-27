from datetime import date, timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views import View
from django.contrib import messages
from django.db.models import Count, Sum, Q
from .models import Subject, StudyTopic, StudySession, StudyNote, DailyStreak
from .forms import SubjectForm, StudyTopicForm
from apps.documents.models import Document
from apps.tutor.models import TutorSession


@method_decorator(login_required, name='dispatch')
class StudyHubView(View):
    """Main 4-tab Study Hub dashboard."""
    def get(self, request):
        tab = request.GET.get('tab', 'overview')
        user = request.user

        # Global stats
        subjects = Subject.objects.filter(user=user)
        total_topics = StudyTopic.objects.filter(subject__user=user).count()
        mastered_topics = StudyTopic.objects.filter(subject__user=user, status='mastered').count()
        total_documents = Document.objects.filter(owner=user).count()
        total_sessions = StudySession.objects.filter(user=user).count()
        total_study_minutes = StudySession.objects.filter(user=user).aggregate(
            total=Sum('duration_minutes')
        )['total'] or 0
        chat_sessions = TutorSession.objects.filter(user=user).count()

        # Streak data
        streak, _ = DailyStreak.objects.get_or_create(user=user)

        # Exam countdown
        upcoming_exams = subjects.filter(
            exam_date__gte=date.today()
        ).order_by('exam_date')[:3]

        # Subject mastery data
        subject_stats = []
        for subj in subjects:
            subject_stats.append({
                'subject': subj,
                'total': subj.topics.count(),
                'mastered': subj.topics.filter(status='mastered').count(),
                'learning': subj.topics.filter(status='learning').count(),
                'percentage': subj.mastery_percentage(),
            })

        context = {
            'tab': tab,
            'subjects': subjects,
            'total_topics': total_topics,
            'mastered_topics': mastered_topics,
            'total_documents': total_documents,
            'total_sessions': total_sessions,
            'total_study_hours': round(total_study_minutes / 60, 1),
            'chat_sessions': chat_sessions,
            'streak': streak,
            'upcoming_exams': upcoming_exams,
            'subject_stats': subject_stats,
        }
        return render(request, 'study/hub.html', context)


@method_decorator(login_required, name='dispatch')
class SubjectCreateView(View):
    def post(self, request):
        form = SubjectForm(request.POST)
        if form.is_valid():
            subject = form.save(commit=False)
            subject.user = request.user
            subject.save()
            messages.success(request, f"Subject '{subject.name}' added!")
        else:
            messages.error(request, "Failed to add subject. Check the form.")
        return redirect('study_hub')


@method_decorator(login_required, name='dispatch')
class SubjectDeleteView(View):
    def post(self, request, subject_id):
        subject = get_object_or_404(Subject, id=subject_id, user=request.user)
        name = subject.name
        subject.delete()
        messages.success(request, f"Subject '{name}' removed.")
        return redirect('study_hub')


@method_decorator(login_required, name='dispatch')
class TopicCreateView(View):
    def post(self, request, subject_id):
        subject = get_object_or_404(Subject, id=subject_id, user=request.user)
        form = StudyTopicForm(request.POST)
        if form.is_valid():
            topic = form.save(commit=False)
            topic.subject = subject
            topic.save()
            messages.success(request, f"Topic '{topic.title}' added to {subject.name}!")
        return redirect(f'{request.path}?tab=subjects')


@method_decorator(login_required, name='dispatch')
class TopicStatusUpdateView(View):
    def post(self, request, topic_id):
        topic = get_object_or_404(StudyTopic, id=topic_id, subject__user=request.user)
        new_status = request.POST.get('status')
        if new_status in ['not_started', 'learning', 'revising', 'mastered']:
            topic.status = new_status
            topic.save()
        return redirect('study_hub')