from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, FileResponse
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.conf import settings
import os
from datetime import datetime

from .forms import CustomUserCreationForm, CustomAuthenticationForm, UserProfileForm
from .models import ResumeRequest, UserProfile


@login_required
def index(request):
    if request.method == "POST":
        employers = request.POST.get("employers", "").strip()
        achievements = request.POST.get("achievements", "").strip()

        if not employers and not achievements:
            messages.error(request, "Пожалуйста, заполните хотя бы одно поле.")
            return render(request, "index.html", {
                "employers": employers,
                "achievements": achievements
            })

        # Сохраняем в сессию
        request.session["employers"] = employers
        request.session["achievements"] = achievements

        # === 🚀 ИМИТАЦИЯ РАБОТЫ LLM-АГЕНТА ===
        # Здесь будет вызов вашего агента
        resume_text = generate_resume_placeholder(employers, achievements, request.user.username)

        # Сохраняем результат в сессию
        request.session["generated_resume"] = resume_text

        # Сохраняем запрос в базу данных
        resume_request = ResumeRequest.objects.create(
            user=request.user,
            employers=employers,
            achievements=achievements,
            resume_content=resume_text
        )

        # Сохраняем ID запроса в сессии для последующего использования
        request.session["last_resume_request_id"] = resume_request.id

        messages.success(request, "Резюме успешно создано!")
        return redirect("result")

    # GET-запрос: показываем форму с сохранёнными данными (если есть)
    employers = request.session.get("employers", "")
    achievements = request.session.get("achievements", "")
    return render(request, "index.html", {
        "employers": employers,
        "achievements": achievements
    })


@login_required
def result(request):
    # Получаем сгенерированное резюме из сессии
    resume = request.session.get("generated_resume", "Резюме не найдено. Вернитесь на главную и создайте его.")

    # Получаем последний запрос для отображения информации
    last_request_id = request.session.get("last_resume_request_id")
    last_request = None
    if last_request_id:
        try:
            last_request = ResumeRequest.objects.get(id=last_request_id, user=request.user)
        except ResumeRequest.DoesNotExist:
            pass

    return render(request, "result.html", {
        "resume": resume,
        "last_request": last_request
    })


@login_required
def history(request):
    """Страница истории запросов"""
    resume_requests = ResumeRequest.objects.filter(user=request.user).order_by('-created_at')

    return render(request, "history.html", {
        "resume_requests": resume_requests
    })


@login_required
def resume_detail(request, request_id):
    """Детальная страница конкретного резюме"""
    resume_request = get_object_or_404(ResumeRequest, id=request_id, user=request.user)

    return render(request, "resume_detail.html", {
        "resume_request": resume_request
    })


@login_required
def download_resume(request, request_id):
    """Скачивание резюме в формате DOCX"""
    resume_request = get_object_or_404(ResumeRequest, id=request_id, user=request.user)

    # Здесь будет вызов вашего агента для генерации DOCX
    # Пока возвращаем текстовый файл
    from django.http import HttpResponse
    response = HttpResponse(resume_request.resume_content, content_type='text/plain')
    response[
        'Content-Disposition'] = f'attachment; filename="resume_{request_id}_{datetime.now().strftime("%Y%m%d")}.txt"'

    return response


@login_required
def profile(request):
    """Страница профиля пользователя"""
    user_profile, created = UserProfile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        form = UserProfileForm(request.POST, instance=user_profile)
        if form.is_valid():
            form.save()
            messages.success(request, 'Профиль успешно обновлен!')
            return redirect('profile')
    else:
        form = UserProfileForm(instance=user_profile)

    # Статистика пользователя
    total_requests = ResumeRequest.objects.filter(user=request.user).count()
    recent_requests = ResumeRequest.objects.filter(user=request.user).order_by('-created_at')[:5]

    return render(request, 'profile.html', {
        'form': form,
        'total_requests': total_requests,
        'recent_requests': recent_requests
    })


def generate_resume_placeholder(employers, achievements, username):
    """Заглушка для генерации резюме (замените на вызов вашего агента)"""
    return (
        f"📄 ПРОФЕССИОНАЛЬНОЕ РЕЗЮМЕ\n"
        f"Сгенерировано: {timezone.now().strftime('%d.%m.%Y %H:%M')}\n"
        f"Пользователь: {username}\n\n"
        f"🎯 ЦЕЛЬ: ПОИСК РАБОТЫ\n\n"
        f"💼 ЖЕЛАЕМЫЕ ДОЛЖНОСТИ И РАБОТОДАТЕЛИ:\n"
        f"{employers if employers else 'Не указано'}\n\n"
        f"🏆 КЛЮЧЕВЫЕ ДОСТИЖЕНИЯ И НАВЫКИ:\n"
        f"{achievements if achievements else 'Не указано'}\n\n"
        f"🔧 ОПЫТ РАБОТЫ:\n"
        f"• Профессиональный опыт будет добавлен агентом ИИ\n"
        f"• Навыки будут структурированы по категориям\n"
        f"• Достижения будут оптимизированы для HR\n\n"
        f"🎓 ОБРАЗОВАНИЕ:\n"
        f"• Информация об образовании будет извлечена из входных данных\n\n"
        f"💡 ДОПОЛНИТЕЛЬНАЯ ИНФОРМАЦИЯ:\n"
        f"Это демо-версия резюме. В реальной системе здесь будет\n"
        f"профессионально составленное резюме от LLM-агента.\n\n"
        f"---\n"
        f"Сгенерировано автоматически ResumeAI"
    )


# Существующие функции аутентификации
def register_view(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()

            # Создаем профиль пользователя
            UserProfile.objects.create(user=user)

            login(request, user)
            messages.success(request, f'Добро пожаловать, {user.username}! Вы успешно зарегистрировались.')
            return redirect('index')
    else:
        form = CustomUserCreationForm()

    return render(request, 'auth/register.html', {'form': form})


def login_view(request):
    if request.method == 'POST':
        form = CustomAuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, f'Добро пожаловать, {username}!')
                next_url = request.GET.get('next', 'index')
                return redirect(next_url)
    else:
        form = CustomAuthenticationForm()

    return render(request, 'auth/login.html', {'form': form})


def logout_view(request):
    logout(request)
    messages.info(request, 'Вы успешно вышли из системы.')
    return redirect('index')


def help_page(request):
    return render(request, "help.html")


def contacts(request):
    return render(request, "contacts.html")


def how_it_works(request):
    return render(request, "how_it_works.html")


def about(request):
    return render(request, "about.html")

