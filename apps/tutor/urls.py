from django.urls import path
from .views import DashboardView, TutorChatView, DocumentsView, QuizzesView

urlpatterns = [
    path('dashboard/', DashboardView.as_view(), name='dashboard'),
    path('chat/', TutorChatView.as_view(), name='tutor_chat'),
    path('documents/', DocumentsView.as_view(), name='documents'),
    path('quizzes/', QuizzesView.as_view(), name='quizzes'),
]