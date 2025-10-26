from django.db import models
from django.contrib.auth.models import User


class ResumeRequest(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='resume_requests')

    # Входные данные
    employers = models.TextField(verbose_name="Работодатели и должности")
    achievements = models.TextField(verbose_name="Достижения и навыки")

    # Результат
    resume_content = models.TextField(verbose_name="Сгенерированное резюме")
    resume_file = models.FileField(upload_to='resumes/', null=True, blank=True, verbose_name="Файл резюме")

    # Метаданные
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")

    class Meta:
        verbose_name = "Запрос резюме"
        verbose_name_plural = "Запросы резюме"
        ordering = ['-created_at']

    def __str__(self):
        return f"Резюме {self.user.username} от {self.created_at.strftime('%d.%m.%Y %H:%M')}"


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')

    # Дополнительные поля пользователя
    phone = models.CharField(max_length=20, blank=True, verbose_name="Телефон")
    profession = models.CharField(max_length=100, blank=True, verbose_name="Основная профессия")

    # Настройки
    default_resume_format = models.CharField(
        max_length=10,
        choices=[('docx', 'DOCX'), ('pdf', 'PDF'), ('txt', 'TXT')],
        default='docx',
        verbose_name="Формат резюме по умолчанию"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Профиль {self.user.username}"

