from django.urls import path
from .views import DashboardView, TutorChatView

urlpatterns = [
    path('dashboard/', DashboardView.as_view(), name='dashboard'),
    path('chat/', TutorChatView.as_view(), name='tutor_chat'),
]