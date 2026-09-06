from django.urls import path

from .api_views import TutorAskView


urlpatterns = [
    path("ask/", TutorAskView.as_view(), name="tutor-ask"),
]

