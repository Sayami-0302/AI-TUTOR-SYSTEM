from datetime import date
import re
import pymupdf
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views import View
from django.contrib import messages
from django.db.models import Sum
from .models import Subject, StudyTopic, StudySession, DailyStreak
from .forms import SubjectForm, StudyTopicForm
from .services import extract_syllabus_with_ai, normalize_topic_title, COLOR_PALETTE
from apps.documents.models import Document
from apps.tutor.models import TutorSession


@method_decorator(login_required, name='dispatch')
class StudyHubView(View):
    def get(self, request):
        tab = request.GET.get('tab', 'overview')
        user = request.user

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

        streak, _ = DailyStreak.objects.get_or_create(user=user)
        upcoming_exams = subjects.filter(exam_date__gte=date.today()).order_by('exam_date')[:3]

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


def is_duplicate_topic(new_title, existing_titles_normalized):
    """
    Smart fuzzy deduplication:
    Checks if new_title's core matches any existing topic's core.
    Uses substring containment so 'Unit 1: OS' matches 'OS – definition'.
    """
    new_core = normalize_topic_title(new_title)
    if not new_core or len(new_core) < 3:
        return False

    for existing_core in existing_titles_normalized:
        # Exact core match
        if new_core == existing_core:
            return True
        # Substring match (one contains the other)
        if len(new_core) > 5 and len(existing_core) > 5:
            if new_core in existing_core or existing_core in new_core:
                return True

    return False


@method_decorator(login_required, name='dispatch')
class ImportSemesterSyllabusView(View):
    def post(self, request):
        doc_id = request.POST.get('document_id')
        if not doc_id:
            messages.error(request, "Please select an uploaded syllabus document.")
            return redirect('/study/?tab=subjects')

        document = get_object_or_404(Document, id=doc_id, owner=request.user)

        extracted_text = ""
        try:
            if hasattr(document, 'content') and document.content.text:
                extracted_text = document.content.text
            elif document.file:
                doc_pdf = pymupdf.open(document.file.path)
                for page in doc_pdf:
                    extracted_text += page.get_text() + "\n"
        except Exception as read_err:
            messages.error(request, f"Could not read document: {str(read_err)}")
            return redirect('/study/?tab=subjects')

        if not extracted_text.strip():
            messages.error(request, "Document appears empty.")
            return redirect('/study/?tab=subjects')

        try:
            syllabus_data = extract_syllabus_with_ai(extracted_text)
        except Exception as ai_err:
            messages.error(request, f"AI Extraction failed: {str(ai_err)}")
            return redirect('/study/?tab=subjects')

        semester = syllabus_data.get('semester', 7)
        subjects_list = syllabus_data.get('subjects', [])

        created_subjects = 0
        skipped_subjects = 0
        updated_subjects = 0
        created_topics = 0

        for idx, subj_data in enumerate(subjects_list):
            name = subj_data.get('name', '').strip()
            code = subj_data.get('code', '').strip() or None
            description = subj_data.get('description', '').strip()
            is_elective = subj_data.get('is_elective', False)
            elective_group = subj_data.get('elective_group') or None
            topics_data = subj_data.get('topics', [])

            if not name:
                continue

            color = COLOR_PALETTE[idx % len(COLOR_PALETTE)]

            existing = Subject.objects.filter(user=request.user, name__iexact=name).first()

            if existing:
                # Get normalized existing topic titles for fuzzy matching
                existing_normalized = {
                    normalize_topic_title(t.title) for t in existing.topics.all()
                }

                missing = []
                for td in topics_data:
                    title = td.get('title', '').strip() if isinstance(td, dict) else str(td).strip()
                    if title and not is_duplicate_topic(title, existing_normalized):
                        missing.append(td)

                if not missing:
                    skipped_subjects += 1
                    continue

                current_ch = existing.topics.count()
                for t_idx, td in enumerate(missing):
                    title = td.get('title', '').strip() if isinstance(td, dict) else str(td).strip()
                    StudyTopic.objects.create(
                        subject=existing,
                        title=title,
                        chapter_number=current_ch + t_idx + 1,
                        difficulty=td.get('difficulty', 'medium') if isinstance(td, dict) else 'medium',
                        status='not_started'
                    )
                    created_topics += 1
                updated_subjects += 1
            else:
                new_subj = Subject.objects.create(
                    user=request.user,
                    name=name,
                    code=code,
                    semester=semester,
                    color=color,
                    description=description,
                    is_elective=is_elective,
                    elective_group=elective_group
                )
                created_subjects += 1

                for t_idx, td in enumerate(topics_data):
                    title = td.get('title', '').strip() if isinstance(td, dict) else str(td).strip()
                    if title:
                        StudyTopic.objects.create(
                            subject=new_subj,
                            title=title,
                            chapter_number=td.get('chapter_number', t_idx + 1) if isinstance(td, dict) else t_idx + 1,
                            difficulty=td.get('difficulty', 'medium') if isinstance(td, dict) else 'medium',
                            status='not_started'
                        )
                        created_topics += 1

        if created_subjects == 0 and created_topics == 0 and skipped_subjects > 0:
            messages.info(request, f"ℹ️ All {skipped_subjects} subjects already up-to-date.")
        else:
            parts = []
            if created_subjects > 0:
                parts.append(f"{created_subjects} new subjects")
            if updated_subjects > 0:
                parts.append(f"{updated_subjects} updated")
            if created_topics > 0:
                parts.append(f"{created_topics} new topics")
            if skipped_subjects > 0:
                parts.append(f"{skipped_subjects} skipped")
            messages.success(request, "🎉 " + ", ".join(parts) + ".")

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
            messages.error(request, "Failed to add subject.")
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
            messages.success(request, f"Topic '{topic.title}' added!")
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