from django.urls import path
from .views import (
    StudyHubView,
    ImportSemesterSyllabusView,
    SubjectCreateView,
    SubjectDeleteView,
    TopicCreateView,
    TopicStatusUpdateView,
)

urlpatterns = [
    path('', StudyHubView.as_view(), name='study_hub'),
    path('import-syllabus/', ImportSemesterSyllabusView.as_view(), name='import_syllabus'),
    path('subject/add/', SubjectCreateView.as_view(), name='subject_add'),
    path('subject/<int:subject_id>/delete/', SubjectDeleteView.as_view(), name='subject_delete'),
    path('subject/<int:subject_id>/topic/add/', TopicCreateView.as_view(), name='topic_add'),
    path('topic/<int:topic_id>/status/', TopicStatusUpdateView.as_view(), name='topic_status'),
]