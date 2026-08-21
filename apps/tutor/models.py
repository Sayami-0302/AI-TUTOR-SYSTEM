from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class TutorSession(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tutor_sessions')
    title = models.CharField(max_length=100, default="New Study Session")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f"{self.title} - {self.user.email} ({self.updated_at.strftime('%Y-%m-%d %H:%M')})"

class ChatMessage(models.Model):
    ROLE_CHOICES = (
        ('user', 'User'),
        ('model', 'AI Tutor'),
    )
    session = models.ForeignKey(TutorSession, on_delete=models.CASCADE, related_name='messages')
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['timestamp']

    def __str__(self):
        return f"{self.role.capitalize()}: {self.content[:30]}..."