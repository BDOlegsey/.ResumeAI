from django.db import models
from django.contrib.auth.models import User
import os
from datetime import datetime


def resume_file_path(instance, filename):
    date_str = datetime.now().strftime('%Y/%m/%d')
    return f'resumes/user_{instance.user.id}/{date_str}/{filename}'


def user_image_path(instance, filename):
    return f'users/user_{instance.user.id}/images/{filename}'


class ResumeRequest(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='resume_requests')
    employers = models.TextField(verbose_name="Работодатели и должности")
    achievements = models.TextField(verbose_name="Достижения и навыки")

    # ДОБАВЛЯЕМ СВЯЗЬ С ИЗОБРАЖЕНИЯМИ
    images = models.ManyToManyField('UserImage', blank=True, verbose_name="Прикрепленные изображения")

    resume_content = models.TextField(verbose_name="Сгенерированное резюме")
    resume_file = models.FileField(upload_to=resume_file_path, null=True, blank=True, verbose_name="Файл резюме (DOCX)")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Резюме {self.user.username} от {self.created_at.strftime('%d.%m.%Y')}"


class UserImage(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to=user_image_path, verbose_name="Изображение")
    title = models.CharField(max_length=255, blank=True, verbose_name="Название изображения")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"Изображение {self.user.username} - {self.title or 'Без названия'}"


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    phone = models.CharField(max_length=20, blank=True)
    profession = models.CharField(max_length=100, blank=True)
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    default_resume_format = models.CharField(max_length=10, choices=[('docx', 'DOCX'), ('pdf', 'PDF'), ('txt', 'TXT')],
                                             default='docx')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Профиль {self.user.username}"