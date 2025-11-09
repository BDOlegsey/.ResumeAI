# [file name]: models.py
from django.db import models
from django.contrib.auth.models import User
import os
from datetime import datetime


def resume_file_path(instance, filename):
    date_str = datetime.now().strftime('%Y/%m/%d')
    return f'resumes/user_{instance.user.id}/{date_str}/{filename}'


def user_image_path(instance, filename):
    return f'users/user_{instance.user.id}/images/{filename}'


def user_portfolio_path(instance, filename):
    return f'users/user_{instance.user.id}/portfolio/{filename}'


class ResumeRequest(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='resume_requests')
    employers = models.TextField(verbose_name="Работодатели и должности")
    achievements = models.TextField(verbose_name="Достижения и навыки")
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


class WorkExperience(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='work_experiences')
    company = models.CharField(max_length=255, verbose_name="Компания")
    position = models.CharField(max_length=255, verbose_name="Должность")
    start_date = models.DateField(verbose_name="Дата начала")
    end_date = models.DateField(null=True, blank=True, verbose_name="Дата окончания")
    currently_working = models.BooleanField(default=False, verbose_name="Работаю сейчас")
    description = models.TextField(blank=True, verbose_name="Обязанности и достижения")

    class Meta:
        ordering = ['-start_date']

    def __str__(self):
        return f"{self.position} в {self.company}"


class Education(models.Model):
    EDUCATION_LEVELS = [
        ('secondary', 'Среднее образование'),
        ('specialized_secondary', 'Среднее специальное'),
        ('bachelor', 'Бакалавр'),
        ('master', 'Магистр'),
        ('phd', 'Кандидат наук'),
        ('doctor', 'Доктор наук'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='educations')
    institution = models.CharField(max_length=255, verbose_name="Учебное заведение")
    degree = models.CharField(max_length=100, choices=EDUCATION_LEVELS, verbose_name="Уровень образования")
    specialty = models.CharField(max_length=255, verbose_name="Специальность")
    start_date = models.DateField(verbose_name="Дата начала")
    end_date = models.DateField(null=True, blank=True, verbose_name="Дата окончания")
    currently_studying = models.BooleanField(default=False, verbose_name="Учусь сейчас")
    description = models.TextField(blank=True, verbose_name="Дополнительная информация")

    class Meta:
        ordering = ['-start_date']

    def __str__(self):
        return f"{self.get_degree_display()} - {self.specialty}"


class PortfolioItem(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='portfolio_items')
    title = models.CharField(max_length=255, verbose_name="Название проекта")
    description = models.TextField(verbose_name="Описание проекта")
    file = models.FileField(upload_to=user_portfolio_path, null=True, blank=True, verbose_name="Файл проекта")
    link = models.URLField(blank=True, verbose_name="Ссылка на проект")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title


class UserProfile(models.Model):
    GENDER_CHOICES = [
        ('male', 'Мужской'),
        ('female', 'Женский'),
        ('other', 'Другое'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')

    # Основная информация
    photo = models.ImageField(upload_to='profile_photos/', null=True, blank=True, verbose_name="Фотография")
    first_name = models.CharField(max_length=100, blank=True, verbose_name="Имя")
    last_name = models.CharField(max_length=100, blank=True, verbose_name="Фамилия")
    middle_name = models.CharField(max_length=100, blank=True, verbose_name="Отчество")
    birth_date = models.DateField(null=True, blank=True, verbose_name="Дата рождения")
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True, verbose_name="Пол")

    # Контакты
    phone = models.CharField(max_length=20, blank=True, verbose_name="Телефон")
    email = models.EmailField(blank=True, verbose_name="Email")
    address = models.CharField(max_length=255, blank=True, verbose_name="Адрес проживания")
    citizenship = models.CharField(max_length=100, blank=True, verbose_name="Гражданство")

    # Профессиональная информация
    profession = models.CharField(max_length=100, blank=True, verbose_name="Основная профессия")
    skills = models.TextField(blank=True, verbose_name="Навыки и умения")
    additional_info = models.TextField(blank=True, verbose_name="Дополнительная информация")

    # Настройки
    default_resume_format = models.CharField(
        max_length=10,
        choices=[('docx', 'DOCX'), ('pdf', 'PDF'), ('txt', 'TXT')],
        default='docx',
        verbose_name="Формат резюме по умолчанию"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Профиль пользователя"
        verbose_name_plural = "Профили пользователей"

    def __str__(self):
        return f"Профиль {self.user.username}"

    @property
    def full_name(self):
        """Возвращает полное ФИО"""
        parts = [self.last_name, self.first_name, self.middle_name]
        return ' '.join(part for part in parts if part).strip()

    @property
    def age(self):
        """Возвращает возраст пользователя"""
        if self.birth_date:
            today = datetime.now().date()
            return today.year - self.birth_date.year - (
                    (today.month, today.day) < (self.birth_date.month, self.birth_date.day)
            )
        return None