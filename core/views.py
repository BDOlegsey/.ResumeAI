# [file name]: views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, FileResponse, Http404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.conf import settings
from django.db import transaction
import os
from datetime import datetime

from .forms import (
    CustomUserCreationForm, CustomAuthenticationForm, UserProfileForm,
    UserImageForm, WorkExperienceForm, EducationForm, PortfolioItemForm
)
from .models import ResumeRequest, UserProfile, UserImage, WorkExperience, Education, PortfolioItem
from .utils.docx_generator import create_resume_docx


@login_required
def profile(request):
    user_profile, created = UserProfile.objects.get_or_create(user=request.user)

    # Получаем связанные данные
    work_experiences = WorkExperience.objects.filter(user=request.user).order_by('-start_date')
    educations = Education.objects.filter(user=request.user).order_by('-start_date')
    portfolio_items = PortfolioItem.objects.filter(user=request.user).order_by('-created_at')

    # Формы
    profile_form = UserProfileForm(request.POST or None, request.FILES or None, instance=user_profile)
    work_exp_form = WorkExperienceForm(request.POST or None)
    education_form = EducationForm(request.POST or None)
    portfolio_form = PortfolioItemForm(request.POST or None, request.FILES or None)

    if request.method == 'POST':
        # Обработка основной формы профиля
        if 'profile_submit' in request.POST and profile_form.is_valid():
            profile_form.save()
            messages.success(request, 'Профиль успешно обновлен!')
            return redirect('profile')

        # Обработка формы опыта работы
        elif 'work_exp_submit' in request.POST and work_exp_form.is_valid():
            work_exp = work_exp_form.save(commit=False)
            work_exp.user = request.user
            work_exp.save()
            messages.success(request, 'Опыт работы добавлен!')
            return redirect('profile')

        # Обработка формы образования
        elif 'education_submit' in request.POST and education_form.is_valid():
            education = education_form.save(commit=False)
            education.user = request.user
            education.save()
            messages.success(request, 'Образование добавлено!')
            return redirect('profile')

        # Обработка формы портфолио
        elif 'portfolio_submit' in request.POST and portfolio_form.is_valid():
            portfolio_item = portfolio_form.save(commit=False)
            portfolio_item.user = request.user
            portfolio_item.save()
            messages.success(request, 'Проект добавлен в портфолио!')
            return redirect('profile')

    # Статистика пользователя
    total_requests = ResumeRequest.objects.filter(user=request.user).count()

    return render(request, 'profile.html', {
        'profile_form': profile_form,
        'work_exp_form': work_exp_form,
        'education_form': education_form,
        'portfolio_form': portfolio_form,
        'work_experiences': work_experiences,
        'educations': educations,
        'portfolio_items': portfolio_items,
        'total_requests': total_requests,
        'user_profile': user_profile,
    })


@login_required
def delete_work_experience(request, experience_id):
    experience = get_object_or_404(WorkExperience, id=experience_id, user=request.user)
    experience.delete()
    messages.success(request, 'Опыт работы удален!')
    return redirect('profile')


@login_required
def delete_education(request, education_id):
    education = get_object_or_404(Education, id=education_id, user=request.user)
    education.delete()
    messages.success(request, 'Образование удалено!')
    return redirect('profile')


@login_required
def delete_portfolio_item(request, item_id):
    item = get_object_or_404(PortfolioItem, id=item_id, user=request.user)
    item.delete()
    messages.success(request, 'Проект удален из портфолио!')
    return redirect('profile')


# ... остальные существующие функции (index, upload_images, etc.) ...
@login_required
def index(request):
    if request.method == "POST":
        employers = request.POST.get("employers", "").strip()
        achievements = request.POST.get("achievements", "").strip()
        selected_images = request.POST.getlist("selected_images")

        print(f"DEBUG: Selected images: {selected_images}")  # ОТЛАДКА

        if not employers and not achievements:
            messages.error(request, "Пожалуйста, заполните хотя бы одно поле.")
            return render(request, "index.html", {
                "employers": employers,
                "achievements": achievements
            })

        request.session["employers"] = employers
        request.session["achievements"] = achievements

        resume_text = generate_resume_placeholder(employers, achievements, request.user.username)
        request.session["generated_resume"] = resume_text

        with transaction.atomic():
            # Создаем запрос резюме
            resume_request = ResumeRequest.objects.create(
                user=request.user,
                employers=employers,
                achievements=achievements,
                resume_content=resume_text
            )

            # ПРИКРЕПЛЯЕМ ВЫБРАННЫЕ ИЗОБРАЖЕНИЯ
            if selected_images:
                try:
                    # Преобразуем ID в целые числа
                    image_ids = [int(img_id) for img_id in selected_images if img_id.isdigit()]
                    print(f"DEBUG: Image IDs: {image_ids}")  # ОТЛАДКА

                    # Получаем изображения пользователя
                    images = UserImage.objects.filter(id__in=image_ids, user=request.user)
                    print(f"DEBUG: Found images: {images.count()}")  # ОТЛАДКА

                    # Добавляем связь ManyToMany
                    resume_request.images.add(*images)
                    messages.info(request, f"Прикреплено {len(images)} изображений к резюме.")

                    # Сохраняем изменения
                    resume_request.save()

                except Exception as e:
                    print(f"DEBUG: Error attaching images: {e}")  # ОТЛАДКА
                    messages.warning(request, f"Ошибка при прикреплении изображений: {str(e)}")

            # Генерируем DOCX
            user_profile = UserProfile.objects.filter(user=request.user).first()
            docx_path = create_resume_docx(resume_request, user_profile)

            if docx_path:
                messages.success(request, "Резюме успешно создано и сохранено в формате DOCX!")
            else:
                messages.warning(request, "Резюме создано, но не удалось сохранить DOCX файл.")

        request.session["last_resume_request_id"] = resume_request.id
        return redirect("result")

    employers = request.session.get("employers", "")
    achievements = request.session.get("achievements", "")
    user_images = UserImage.objects.filter(user=request.user).order_by('-uploaded_at')

    return render(request, "index.html", {
        "employers": employers,
        "achievements": achievements,
        "user_images": user_images,
    })


@login_required
def upload_images(request):
    """Загрузка изображений - упрощенная версия"""
    if request.method == 'POST' and request.FILES:
        images = request.FILES.getlist('images')

        if not images:
            messages.error(request, 'Пожалуйста, выберите файлы для загрузки.')
            return redirect('index')

        uploaded_count = 0
        errors = []

        for image_file in images:
            try:
                # Проверка размера
                if image_file.size > 5 * 1024 * 1024:
                    errors.append(f"Файл {image_file.name} слишком большой (макс. 5MB)")
                    continue

                # Проверка типа
                ext = os.path.splitext(image_file.name)[1].lower().lstrip('.')
                if ext not in ['jpg', 'jpeg', 'png', 'gif', 'bmp']:
                    errors.append(f"Файл {image_file.name} должен быть изображением (JPG, PNG, GIF, BMP)")
                    continue

                # Проверка что это действительно изображение
                try:
                    from PIL import Image
                    img = Image.open(image_file)
                    img.verify()
                    image_file.seek(0)  # Reset file pointer
                except Exception:
                    errors.append(f"Файл {image_file.name} не является корректным изображением")
                    continue

                # Сохраняем изображение
                UserImage.objects.create(
                    user=request.user,
                    image=image_file,
                    title=os.path.splitext(image_file.name)[0]
                )
                uploaded_count += 1

            except Exception as e:
                errors.append(f"Ошибка при загрузке {image_file.name}: {str(e)}")

        if uploaded_count > 0:
            messages.success(request, f'Успешно загружено {uploaded_count} изображений.')

        for error in errors:
            messages.error(request, error)

    return redirect('index')


@login_required
def delete_image(request, image_id):
    image = get_object_or_404(UserImage, id=image_id, user=request.user)
    image_title = image.title or "Изображение"
    image.delete()
    messages.success(request, f'Изображение "{image_title}" удалено.')
    return redirect('index')


@login_required
def result(request):
    resume = request.session.get("generated_resume", "Резюме не найдено. Вернитесь на главную и создайте его.")
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
    resume_requests = ResumeRequest.objects.filter(user=request.user).order_by('-created_at')
    return render(request, "history.html", {
        "resume_requests": resume_requests
    })


@login_required
def resume_detail(request, request_id):
    resume_request = get_object_or_404(ResumeRequest, id=request_id, user=request.user)
    return render(request, "resume_detail.html", {
        "resume_request": resume_request
    })


@login_required
def download_resume(request, request_id):
    resume_request = get_object_or_404(ResumeRequest, id=request_id, user=request.user)

    if resume_request.resume_file:
        response = FileResponse(
            resume_request.resume_file.open(),
            as_attachment=True,
            filename=f"resume_{resume_request.user.username}_{resume_request.created_at.strftime('%Y%m%d')}.docx"
        )
        return response
    else:
        response = HttpResponse(resume_request.resume_content, content_type='text/plain')
        response[
            'Content-Disposition'] = f'attachment; filename="resume_{request_id}_{datetime.now().strftime("%Y%m%d")}.txt"'
        return response


@login_required
def view_resume_file(request, request_id):
    resume_request = get_object_or_404(ResumeRequest, id=request_id, user=request.user)

    if not resume_request.resume_file:
        raise Http404("Файл резюме не найден")

    return FileResponse(
        resume_request.resume_file.open(),
        filename=os.path.basename(resume_request.resume_file.name)
    )


def generate_resume_placeholder(employers, achievements, username):
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


def register_view(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
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


# [file name]: views.py
# ДОБАВЛЯЕМ ЭТИ ФУНКЦИИ В КОНЕЦ ФАЙЛА, ПЕРЕД СУЩЕСТВУЮЩИЕ ФУНКЦИИ (help_page, contacts и т.д.)

@login_required
def edit_work_experience(request, experience_id):
    """Редактирование опыта работы"""
    experience = get_object_or_404(WorkExperience, id=experience_id, user=request.user)

    if request.method == 'POST':
        form = WorkExperienceForm(request.POST, instance=experience)
        if form.is_valid():
            form.save()
            messages.success(request, 'Опыт работы успешно обновлен!')
            return redirect('profile')
    else:
        form = WorkExperienceForm(instance=experience)

    return render(request, 'edit_work_experience.html', {
        'form': form,
        'experience': experience,
    })


@login_required
def edit_education(request, education_id):
    """Редактирование образования"""
    education = get_object_or_404(Education, id=education_id, user=request.user)

    if request.method == 'POST':
        form = EducationForm(request.POST, instance=education)
        if form.is_valid():
            form.save()
            messages.success(request, 'Образование успешно обновлено!')
            return redirect('profile')
    else:
        form = EducationForm(instance=education)

    return render(request, 'edit_education.html', {
        'form': form,
        'education': education,
    })


@login_required
def edit_portfolio_item(request, item_id):
    """Редактирование проекта в портфолио"""
    item = get_object_or_404(PortfolioItem, id=item_id, user=request.user)

    if request.method == 'POST':
        form = PortfolioItemForm(request.POST, request.FILES, instance=item)
        if form.is_valid():
            form.save()
            messages.success(request, 'Проект успешно обновлен!')
            return redirect('profile')
    else:
        form = PortfolioItemForm(instance=item)

    return render(request, 'edit_portfolio_item.html', {
        'form': form,
        'item': item,
    })
