# [file name]: forms.py
from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.models import User
from .models import UserProfile, UserImage, WorkExperience, Education, PortfolioItem
import os
from PIL import Image


class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True, label="Email")

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in self.fields:
            self.fields[field_name].widget.attrs.update({
                'class': 'form-control',
                'placeholder': self.fields[field_name].label
            })


class CustomAuthenticationForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in self.fields:
            self.fields[field_name].widget.attrs.update({
                'class': 'form-control',
                'placeholder': self.fields[field_name].label
            })


class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = [
            'photo', 'first_name', 'last_name', 'middle_name', 'birth_date', 'gender',
            'phone', 'email', 'address', 'citizenship',
            'profession', 'skills', 'additional_info',
            'default_resume_format'
        ]
        widgets = {
            'photo': forms.FileInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Имя'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Фамилия'}),
            'middle_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Отчество'}),
            'birth_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
                'placeholder': 'дд.мм.гггг'
            }),
            'gender': forms.Select(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+7 (XXX) XXX-XX-XX'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'example@email.com'}),
            'address': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Город, страна'}),
            'citizenship': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Гражданство'}),
            'profession': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Основная профессия'}),
            'skills': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Перечислите ваши навыки через запятую',
                'rows': 4
            }),
            'additional_info': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Дополнительная информация о себе',
                'rows': 4
            }),
            'default_resume_format': forms.Select(attrs={'class': 'form-control'}),
        }
        labels = {
            'photo': '📷 Фотография профиля',
            'first_name': '👤 Имя',
            'last_name': '👤 Фамилия',
            'middle_name': '👤 Отчество',
            'birth_date': '🎂 Дата рождения',
            'gender': '⚧ Пол',
            'phone': '📞 Телефон',
            'email': '📧 Email',
            'address': '🏠 Адрес проживания',
            'citizenship': '🌍 Гражданство',
            'profession': '💼 Профессия',
            'skills': '🛠️ Навыки и умения',
            'additional_info': '📝 Дополнительная информация',
            'default_resume_format': '📄 Формат резюме по умолчанию',
        }


class WorkExperienceForm(forms.ModelForm):
    class Meta:
        model = WorkExperience
        fields = ['company', 'position', 'start_date', 'end_date', 'currently_working', 'description']
        widgets = {
            'company': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Название компании'}),
            'position': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Должность'}),
            'start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'end_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'currently_working': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Обязанности, достижения, проекты...',
                'rows': 4
            }),
        }
        labels = {
            'company': '🏢 Компания',
            'position': '💼 Должность',
            'start_date': '📅 Дата начала',
            'end_date': '📅 Дата окончания',
            'currently_working': '✅ Работаю сейчас',
            'description': '📋 Обязанности и достижения',
        }

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        currently_working = cleaned_data.get('currently_working')

        if start_date and end_date and start_date > end_date:
            raise forms.ValidationError("Дата начала не может быть позже даты окончания")

        if currently_working and end_date:
            raise forms.ValidationError("Если вы работаете сейчас, дата окончания должна быть пустой")

        return cleaned_data


class EducationForm(forms.ModelForm):
    class Meta:
        model = Education
        fields = ['institution', 'degree', 'specialty', 'start_date', 'end_date', 'currently_studying', 'description']
        widgets = {
            'institution': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Название учебного заведения'}),
            'degree': forms.Select(attrs={'class': 'form-control'}),
            'specialty': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Специальность'}),
            'start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'end_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'currently_studying': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Курсы, достижения, средний балл...',
                'rows': 3
            }),
        }
        labels = {
            'institution': '🎓 Учебное заведение',
            'degree': '📚 Уровень образования',
            'specialty': '📖 Специальность',
            'start_date': '📅 Дата начала',
            'end_date': '📅 Дата окончания',
            'currently_studying': '✅ Учусь сейчас',
            'description': '📋 Дополнительная информация',
        }

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        currently_studying = cleaned_data.get('currently_studying')

        if start_date and end_date and start_date > end_date:
            raise forms.ValidationError("Дата начала не может быть позже даты окончания")

        if currently_studying and end_date:
            raise forms.ValidationError("Если вы учитесь сейчас, дата окончания должна быть пустой")

        return cleaned_data

class PortfolioItemForm(forms.ModelForm):
    class Meta:
        model = PortfolioItem
        fields = ['title', 'description', 'file', 'link']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Название проекта'}),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Описание проекта, используемые технологии...',
                'rows': 4
            }),
            'file': forms.FileInput(attrs={'class': 'form-control'}),
            'link': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://example.com'}),
        }
        labels = {
            'title': '📁 Название проекта',
            'description': '📝 Описание проекта',
            'file': '📎 Файл проекта',
            'link': '🔗 Ссылка на проект',
        }


class UserImageForm(forms.ModelForm):
    class Meta:
        model = UserImage
        fields = ['image', 'title']
        widgets = {
            'image': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*'
            }),
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Название изображения (опционально)'
            }),
        }
