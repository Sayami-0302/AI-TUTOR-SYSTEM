from datetime import date
import pymupdf
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views import View
from django.contrib import messages
from django.db.models import Sum
from .models import Subject, StudyTopic, StudySession, DailyStreak
from .forms import SubjectForm, StudyTopicForm
from .services import extract_syllabus_with_ai, COLOR_PALETTE
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
        user_documents = Document.objects.filter(owner=user)
        total_topics = StudyTopic.objects.filter(subject__user=user).count()
        mastered_topics = StudyTopic.objects.filter(subject__user=user, status='mastered').count()
        total_documents = user_documents.count()
        total_sessions = StudySession.objects.filter(user=user).count()
        total_study_minutes = StudySession.objects.filter(user=user).aggregate(
            total=Sum('duration_minutes')
        )['total'] or 0
        chat_sessions = TutorSession.objects.filter(user=user).count()

        # Streak data
        streak, _ = DailyStreak.objects.get_or_create(user=user)

        # Upcoming Exams
        upcoming_exams = subjects.filter(
            exam_date__gte=date.today()
        ).order_by('exam_date')[:3]

        context = {
            'tab': tab,
            'subjects': subjects,
            'user_documents': user_documents,
            'total_topics': total_topics,
            'mastered_topics': mastered_topics,
            'total_documents': total_documents,
            'total_sessions': total_sessions,
            'total_study_hours': round(total_study_minutes / 60, 1),
            'chat_sessions': chat_sessions,
            'streak': streak,
            'upcoming_exams': upcoming_exams,
        }
        return render(request, 'study/hub.html', context)


@method_decorator(login_required, name='dispatch')
class ImportSemesterSyllabusView(View):
    """Extracts all subjects & topics from an uploaded syllabus PDF using AI."""
    def post(self, request):
        doc_id = request.POST.get('document_id')
        if not doc_id:
            messages.error(request, "Please select an uploaded syllabus document.")
            return redirect('/study/?tab=subjects')

        document = get_object_or_404(Document, id=doc_id, owner=request.user)

        # 1. Extract text from document
        extracted_text = ""
        try:
            if hasattr(document, 'content') and document.content.text:
                extracted_text = document.content.text
            elif document.file:
                doc_pdf = pymupdf.open(document.file.path)
                for page in doc_pdf:
                    extracted_text += page.get_text() + "\n"
        except Exception as read_err:
            messages.error(request, f"Could not read text from document: {str(read_err)}")
            return redirect('/study/?tab=subjects')

        if not extracted_text.strip():
            messages.error(request, "The selected document appears to be empty or contains no readable text.")
            return redirect('/study/?tab=subjects')

        # 2. Call AI to extract structured syllabus data
        try:
            syllabus_data = extract_syllabus_with_ai(extracted_text)
        except Exception as ai_err:
            messages.error(request, f"AI Syllabus Extraction failed: {str(ai_err)}")
            return redirect('/study/?tab=subjects')

        # 3. Save extracted subjects and topics safely without duplicate key collisions
        semester = syllabus_data.get('semester', 7)
        subjects_list = syllabus_data.get('subjects', [])

        created_subjects_count = 0
        created_topics_count = 0

        for idx, subj_data in enumerate(subjects_list):
            name = subj_data.get('name', '').strip()
            code = subj_data.get('code', '').strip() or None
            description = subj_data.get('description', '').strip()
            topics_data = subj_data.get('topics', [])

            if not name:
                continue

            color = COLOR_PALETTE[idx % len(COLOR_PALETTE)]

            # Safe lookup by name for this user
            subject = Subject.objects.filter(user=request.user, name__iexact=name).first()
            if not subject:
                subject = Subject.objects.create(
                    user=request.user,
                    name=name,
                    code=code,
                    semester=semester,
                    color=color,
                    description=description
                )
                created_subjects_count += 1
            else:
                # Update code and description if missing
                if code and not subject.code:
                    subject.code = code
                    subject.save()

            # Insert topics safely
            for t_idx, topic_data in enumerate(topics_data):
                topic_title = topic_data.get('title', '').strip()
                difficulty = topic_data.get('difficulty', 'medium')
                chapter_num = topic_data.get('chapter_number', t_idx + 1)

                if topic_title:
                    existing_topic = StudyTopic.objects.filter(subject=subject, title__iexact=topic_title).first()
                    if not existing_topic:
                        StudyTopic.objects.create(
                            subject=subject,
                            title=topic_title,
                            chapter_number=chapter_num,
                            difficulty=difficulty,
                            status='not_started'
                        )
                        created_topics_count += 1

        messages.success(
            request, 
            f"🎉 Success! AI generated/synced {created_subjects_count} new subjects and {created_topics_count} topics from your syllabus."
        )
        return redirect('/study/?tab=subjects')


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
        return redirect('/study/?tab=subjects')


@method_decorator(login_required, name='dispatch')
class SubjectDeleteView(View):
    def post(self, request, subject_id):
        subject = get_object_or_404(Subject, id=subject_id, user=request.user)
        name = subject.name
        subject.delete()
        messages.success(request, f"Subject '{name}' removed.")
        return redirect('/study/?tab=subjects')


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
        return redirect('/study/?tab=subjects')


@method_decorator(login_required, name='dispatch')
class TopicStatusUpdateView(View):
    def post(self, request, topic_id):
        topic = get_object_or_404(StudyTopic, id=topic_id, subject__user=request.user)
        new_status = request.POST.get('status')
        if new_status in ['not_started', 'learning', 'revising', 'mastered']:
            topic.status = new_status
            topic.save()
        return redirect('/study/?tab=subjects')