import uuid
from django.contrib.auth.models import AbstractUser
from django.db import models

class CustomUser(AbstractUser):
    # 아이디는 AbstractUser의 username을 사용하고, 비밀번호는 password를 사용합니다.
    name = models.CharField(max_length=100, verbose_name="이름")
    unique_code = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, verbose_name="고유코드")

    def __str__(self):
        return f"{self.username} ({self.name})"
