import io
import json
import logging
import os
from datetime import datetime

from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, FileResponse, Http404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.conf import settings
from django.db import transaction

from .forms import (
    CustomUserCreationForm, CustomAuthenticationForm, UserProfileForm,
    UserImageForm, WorkExperienceForm, EducationForm, PortfolioItemForm,
    ResumeGenerationForm
)
from .models import ResumeRequest, ResumeResult, UserProfile, UserImage, WorkExperience, Education, PortfolioItem
from .agents.pipeline import run_resume_pipeline
from .agents.preprocess_agent import validate_profile

logger = logging.getLogger('core')

@login_required
def profile(request):
    user_profile, _ = UserProfile.objects.get_or_create(user=request.user)
    work_experiences = WorkExperience.objects.filter(user=request.user).order_by('-start_date')
    educations = Education.objects.filter(user=request.user).order_by('-start_date')
    portfolio_items = PortfolioItem.objects.filter(user=request.user).order_by('-created_at')

    profile_form = UserProfileForm(request.POST or None, request.FILES or None, instance=user_profile)
    work_exp_form = WorkExperienceForm(request.POST or None)
    education_form = EducationForm(request.POST or None)
    portfolio_form = PortfolioItemForm(request.POST or None, request.FILES or None)

    if request.method == 'POST':
        if 'profile_submit' in request.POST and profile_form.is_valid():
            user_profile = profile_form.save()
            logger.info("User %s updated profile", request.user.username)
            # Предобработка профиля агентом на адекватность
            warnings = validate_profile(user_profile)
            if warnings:
                for w in warnings:
                    messages.warning(request, w)
            messages.success(request, 'Профиль успешно обновлен!')
            return redirect('profile')
        elif 'work_exp_submit' in request.POST and work_exp_form.is_valid():
            work_exp = work_exp_form.save(commit=False)
            work_exp.user = request.user
            work_exp.save()
            messages.success(request, 'Опыт работы добавлен!')
            return redirect('profile')
        elif 'education_submit' in request.POST and education_form.is_valid():
            education = education_form.save(commit=False)
            education.user = request.user
            education.save()
            messages.success(request, 'Образование добавлено!')
            return redirect('profile')
        elif 'portfolio_submit' in request.POST and portfolio_form.is_valid():
            item = portfolio_form.save(commit=False)
            item.user = request.user
            item.save()
            messages.success(request, 'Проект добавлен в портфолио!')
            return redirect('profile')

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
def index(request):
    if request.method == "POST":
        form = ResumeGenerationForm(request.POST, user=request.user)
        if not form.is_valid():
            messages.error(request, "Проверьте корректность формы.")
            return render(request, "index.html", {"form": form})

        targets = form.parse_targets()
        extra_instructions = form.cleaned_data['extra_instructions']
        strict_matching = form.cleaned_data['strict_matching']
        add_skills = form.cleaned_data['add_skills']
        specific_conditions = form.cleaned_data['specific_conditions']
        selected_images = form.cleaned_data.get('selected_images') or []

        with transaction.atomic():
            resume_request = ResumeRequest.objects.create(
                user=request.user,
                employers="\n".join([t['company'] + (f" — {t['role']}" if t['role'] else "") for t in targets]),
                achievements=extra_instructions or "",
                targets=targets,
                extra_instructions=extra_instructions,
                strict_matching=strict_matching,
                add_skills=add_skills,
                specific_conditions=specific_conditions,
                status=ResumeRequest.Status.PENDING
            )

            if selected_images:
                image_ids = [int(x) for x in selected_images if str(x).isdigit()]
                images = UserImage.objects.filter(id__in=image_ids, user=request.user)
                resume_request.images.add(*images)
                messages.info(request, f"Прикреплено {images.count()} изображений к запросу.")

        # Запуск мультиагентного пайплайна
        try:
            resume_request.status = ResumeRequest.Status.RUNNING
            resume_request.save(update_fields=['status'])
            archive_path = run_resume_pipeline(request.user, resume_request)
            if archive_path:
                from django.core.files.base import File
                with open(archive_path, 'rb') as f:
                    resume_request.archive_file.save(os.path.basename(archive_path), File(f), save=False)
            resume_request.status = ResumeRequest.Status.DONE
            resume_request.save()
            messages.success(request, "Генерация резюме завершена. Доступен архив для скачивания.")
        except Exception as e:
            logger.exception("Pipeline failed: %s", e)
            resume_request.status = ResumeRequest.Status.FAILED
            resume_request.error = str(e)
            resume_request.save()
            messages.error(request, f"Ошибка генерации: {e}")

        request.session["last_resume_request_id"] = resume_request.id
        return redirect("result")

    form = ResumeGenerationForm(user=request.user)
    return render(request, "index.html", {"form": form})

@login_required
def result(request):
    last_request_id = request.session.get("last_resume_request_id")
    last_request = None
    if last_request_id:
        try:
            last_request = ResumeRequest.objects.get(id=last_request_id, user=request.user)
        except ResumeRequest.DoesNotExist:
            last_request = None
    return render(request, "result.html", {"last_request": last_request})

@login_required
def history(request):
    resume_requests = ResumeRequest.objects.filter(user=request.user).order_by('-created_at')
    return render(request, "history.html", {"resume_requests": resume_requests})

@login_required
def resume_detail(request, request_id):
    resume_request = get_object_or_404(ResumeRequest, id=request_id, user=request.user)
    results = resume_request.results.all().order_by('-created_at')
    return render(request, "resume_detail.html", {"resume_request": resume_request, "results": results})

@login_required
def download_archive(request, request_id):
    resume_request = get_object_or_404(ResumeRequest, id=request_id, user=request.user)
    if not resume_request.archive_file:
        raise Http404("Архив не найден")
    return FileResponse(resume_request.archive_file.open('rb'), as_attachment=True, filename=os.path.basename(resume_request.archive_file.name))

@login_required
def view_archive_file(request, request_id):
    resume_request = get_object_or_404(ResumeRequest, id=request_id, user=request.user)
    if not resume_request.archive_file:
        raise Http404("Архив не найден")
    return FileResponse(resume_request.archive_file.open('rb'), filename=os.path.basename(resume_request.archive_file.name))

@login_required
def download_result_docx(request, result_id):
    result = get_object_or_404(ResumeResult, id=result_id, request__user=request.user)
    if not result.docx_file:
        raise Http404("DOCX не найден")
    return FileResponse(result.docx_file.open('rb'), as_attachment=True, filename=os.path.basename(result.docx_file.name))

@login_required
def download_result_json(request, result_id):
    result = get_object_or_404(ResumeResult, id=result_id, request__user=request.user)
    if not result.json_file:
        data = json.dumps(result.json_data or {}, ensure_ascii=False, indent=2)
        resp = HttpResponse(data, content_type='application/json; charset=utf-8')
        resp['Content-Disposition'] = f'attachment; filename="resume_{result.id}.json"'
        return resp
    return FileResponse(result.json_file.open('rb'), as_attachment=True, filename=os.path.basename(result.json_file.name))

@login_required
def upload_images(request):
    if request.method == 'POST' and request.FILES:
        images = request.FILES.getlist('images')
        if not images:
            messages.error(request, 'Пожалуйста, выберите файлы для загрузки.')
            return redirect('index')
        uploaded_count, errors = 0, []
        for image_file in images:
            try:
                if image_file.size > settings.MAX_UPLOAD_SIZE:
                    errors.append(f"Файл {image_file.name} слишком большой (макс. 5MB)")
                    continue
                ext = os.path.splitext(image_file.name)[1].lower().lstrip('.')
                if ext not in settings.ALLOWED_IMAGE_EXTENSIONS:
                    errors.append(f"Файл {image_file.name} должен быть изображением (JPG, PNG, GIF, BMP)")
                    continue
                try:
                    from PIL import Image
                    img = Image.open(image_file)
                    img.verify()
                    image_file.seek(0)
                except Exception:
                    errors.append(f"Файл {image_file.name} не является корректным изображением")
                    continue
                UserImage.objects.create(user=request.user, image=image_file, title=os.path.splitext(image_file.name)[0])
                uploaded_count += 1
            except Exception as e:
                errors.append(f"Ошибка при загрузке {image_file.name}: {str(e)}")
        if uploaded_count > 0:
            messages.success(request, f'Успешно загружено {uploaded_count} изображений.')
        for error in errors:
            messages.error(request, error)
        return redirect('index')
    return redirect('index')

@login_required
def delete_image(request, image_id):
    image = get_object_or_404(UserImage, id=image_id, user=request.user)
    title = image.title or "Изображение"
    image.delete()
    messages.success(request, f'Изображение "{title}" удалено.')
    return redirect('index')

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

@login_required
def edit_work_experience(request, experience_id):
    experience = get_object_or_404(WorkExperience, id=experience_id, user=request.user)
    if request.method == 'POST':
        form = WorkExperienceForm(request.POST, instance=experience)
        if form.is_valid():
            form.save()
            messages.success(request, 'Опыт работы успешно обновлен!')
            return redirect('profile')
    else:
        form = WorkExperienceForm(instance=experience)
    return render(request, 'edit_work_experience.html', {'form': form, 'experience': experience})

@login_required
def edit_education(request, education_id):
    education = get_object_or_404(Education, id=education_id, user=request.user)
    if request.method == 'POST':
        form = EducationForm(request.POST, instance=education)
        if form.is_valid():
            form.save()
            messages.success(request, 'Образование успешно обновлено!')
            return redirect('profile')
    else:
        form = EducationForm(instance=education)
    return render(request, 'edit_education.html', {'form': form, 'education': education})

@login_required
def edit_portfolio_item(request, item_id):
    item = get_object_or_404(PortfolioItem, id=item_id, user=request.user)
    if request.method == 'POST':
        form = PortfolioItemForm(request.POST, request.FILES, instance=item)
        if form.is_valid():
            form.save()
            messages.success(request, 'Проект успешно обновлен!')
            return redirect('profile')
    else:
        form = PortfolioItemForm(instance=item)
    return render(request, 'edit_portfolio_item.html', {'form': form, 'item': item})
