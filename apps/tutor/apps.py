from django.apps import AppConfig


class TutorConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.tutor'   #  Points to apps/tutor folder
    label = 'tutor'       #  Tells Django to recognize it simply as 'tutor'