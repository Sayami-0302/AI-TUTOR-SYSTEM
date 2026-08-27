from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from django.db.models import Q

User = get_user_model()


class EmailBackend(ModelBackend):
    """
    Custom authentication backend that allows users to log in
    using their email address or username with case-insensitive matching.
    """
    def authenticate(self, request, username=None, password=None, email=None, **kwargs):
        login_credential = email or username
        if not login_credential or not password:
            return None

        try:
            # Match by email or username (case-insensitive)
            user = User.objects.get(
                Q(email__iexact=login_credential) | Q(username__iexact=login_credential)
            )
        except User.DoesNotExist:
            return None
        except User.MultipleObjectsReturned:
            user = User.objects.filter(
                Q(email__iexact=login_credential) | Q(username__iexact=login_credential)
            ).order_by('id').first()

        if user and user.check_password(password):
            return user
        return None