from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    username = models.CharField(max_length=150, unique=True)
    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=255)
    

    USERNAME_FIELD="email"
    REQUIRED_FIELDS=["username","full_name"]

    def __str__(self):
        return self.email