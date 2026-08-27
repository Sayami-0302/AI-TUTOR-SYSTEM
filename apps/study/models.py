from django.db import models
from django.contrib.auth import get_user_model
from apps.documents.models import Document

User = get_user_model()


class Subject(models.Model):
    """A course/subject the student is studying this semester."""
    SEMESTER_CHOICES = [(i, f"Semester {i}") for i in range(1, 9)]

    COLOR_CHOICES = [
        ('indigo', 'Indigo'),
        ('emerald', 'Emerald'),
        ('rose', 'Rose'),
        ('amber', 'Amber'),
        ('sky', 'Sky'),
        ('violet', 'Violet'),
        ('orange', 'Orange'),
        ('teal', 'Teal'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='subjects')
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=20, blank=True, help_text="e.g. CS401")
    semester = models.IntegerField(choices=SEMESTER_CHOICES, default=7)
    color = models.CharField(max_length=10, choices=COLOR_CHOICES, default='indigo')
    description = models.TextField(blank=True)
    exam_date = models.DateField(null=True, blank=True, help_text="Exam countdown target")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['semester', 'name']
        unique_together = ['user', 'code']

    def __str__(self):
        return f"{self.code} - {self.name}" if self.code else self.name

    def topic_count(self):
        return self.topics.count()

    def mastery_percentage(self):
        total = self.topics.count()
        if total == 0:
            return 0
        mastered = self.topics.filter(status='mastered').count()
        return int((mastered / total) * 100)


class StudyTopic(models.Model):
    """A specific topic/chapter within a subject."""
    STATUS_CHOICES = [
        ('not_started', 'Not Started'),
        ('learning', 'Learning'),
        ('revising', 'Revising'),
        ('mastered', 'Mastered'),
    ]

    DIFFICULTY_CHOICES = [
        ('easy', 'Easy'),
        ('medium', 'Medium'),
        ('hard', 'Hard'),
    ]

    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='topics')
    title = models.CharField(max_length=300)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='not_started')
    difficulty = models.CharField(max_length=10, choices=DIFFICULTY_CHOICES, default='medium')
    chapter_number = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['chapter_number', 'title']

    def __str__(self):
        return f"{self.subject.code}: {self.title}"


class StudySession(models.Model):
    """Tracks every study session for analytics and streaks."""
    SESSION_TYPES = [
        ('chat', 'AI Tutor Chat'),
        ('quiz', 'Quiz'),
        ('flashcard', 'Flashcard Review'),
        ('revision', 'Revision Queue'),
        ('reading', 'Document Reading'),
        ('notes', 'Note Making'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='study_sessions')
    subject = models.ForeignKey(Subject, on_delete=models.SET_NULL, null=True, blank=True)
    session_type = models.CharField(max_length=15, choices=SESSION_TYPES)
    duration_minutes = models.PositiveIntegerField(default=0)
    notes = models.TextField(blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-started_at']

    def __str__(self):
        return f"{self.user.username} - {self.get_session_type_display()} ({self.duration_minutes}min)"


class StudyNote(models.Model):
    """AI-generated or manual study notes linked to documents."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='study_notes')
    subject = models.ForeignKey(Subject, on_delete=models.SET_NULL, null=True, blank=True)
    document = models.ForeignKey(Document, on_delete=models.SET_NULL, null=True, blank=True)
    title = models.CharField(max_length=300)
    content = models.TextField(help_text="Markdown-formatted study notes")
    ai_generated = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title


class DailyStreak(models.Model):
    """Tracks daily study streaks for gamification."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='streak')
    current_streak = models.PositiveIntegerField(default=0)
    longest_streak = models.PositiveIntegerField(default=0)
    total_xp = models.PositiveIntegerField(default=0)
    last_study_date = models.DateField(null=True, blank=True)
    level = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f"{self.user.username} - Streak: {self.current_streak} days, XP: {self.total_xp}"