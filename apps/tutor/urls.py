from django.urls import path
from .views import (
    DashboardView, 
    TutorChatView, 
    NewSessionView, 
    ClearSessionView, 
    DocumentsView, 
    QuizzesView
)

urlpatterns = [
    path('dashboard/', DashboardView.as_view(), name='dashboard'),
    path('chat/', TutorChatView.as_view(), name='tutor_chat'),
    path('chat/<int:session_id>/', TutorChatView.as_view(), name='tutor_chat_session'),
    path('chat/new/', NewSessionView.as_view(), name='new_session'),
    path('chat/<int:session_id>/clear/', ClearSessionView.as_view(), name='clear_session'),
    path('documents/', DocumentsView.as_view(), name='documents'),
    path('quizzes/', QuizzesView.as_view(), name='quizzes'),
]