from django.shortcuts import render, redirect, get_object_or_404
from django.http import FileResponse, HttpResponse, Http404
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.core.files.base import ContentFile
import os
from datetime import datetime

from .forms import CustomUserCreationForm, CustomAuthenticationForm, UserProfileForm
from .models import ResumeRequest, UserProfile, UserImage

from .resumeai.models import UserData
from .resumeai.pipeline import generate_resume_docx


@login_required
def index(request):
    if request.method == "POST":
        job_title = request.POST.get("job_title", "").strip()
        employers = request.POST.get("employers", "").strip()
        achievements = request.POST.get("achievements", "").strip()
        selected_images = request.POST.getlist("selected_images")

        if not job_title or not employers or not achievements:
            messages.error(request, "Заполните все обязательные поля.")
            return render(request, "index.html", {
                "job_title": job_title,
                "employers": employers,
                "achievements": achievements,
                "user_images": UserImage.objects.filter(user=request.user).order_by('-uploaded_at'),
            })

        # Парсим список компаний
        employers_list = []
        for line in employers.replace(",", "\n").splitlines():
            line = line.strip()
            if line:
                employers_list.append(line)

        if not employers_list:
            messages.error(request, "Укажите хотя бы одну компанию.")
            return redirect("index")

        user_data = UserData(
            employers=employers_list,
            job_title=job_title,
            experience="",
            skills="",
            achievements=achievements,
            attachments=[]
        )

        # Генерация резюме
        try:
            resume_text, zip_bytes, _ = generate_resume_docx(user_data, max_iterations=3)
        except Exception as e:
            messages.error(request, f"Ошибка генерации резюме: {e}")
            return redirect("index")

        # Сохранение в БД
        with transaction.atomic():
            resume_request = ResumeRequest.objects.create(
                user=request.user,
                job_title=job_title,
                employers="\n".join(employers_list),
                achievements=achievements,
                resume_content=resume_text
            )

            if selected_images:
                image_ids = [int(img_id) for img_id in selected_images if str(img_id).isdigit()]
                images = UserImage.objects.filter(id__in=image_ids, user=request.user)
                resume_request.images.add(*list(images))

            # Сохраняем ZIP-архив
            filename = f"resumes_{request.user.username}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
            resume_request.resume_file.save(filename, ContentFile(zip_bytes), save=True)

        request.session["last_resume_request_id"] = resume_request.id
        messages.success(request, f"Создано {len(employers_list)} резюме!")
        return redirect("result")

    user_images = UserImage.objects.filter(user=request.user).order_by(
        '-uploaded_at') if request.user.is_authenticated else []
    return render(request, "index.html", {"user_images": user_images})


@login_required
def upload_images(request):
    if request.method == 'POST' and request.FILES:
        images = request.FILES.getlist('images')
        uploaded_count = 0

        for image_file in images:
            try:
                if image_file.size > 5 * 1024 * 1024:
                    continue
                UserImage.objects.create(
                    user=request.user,
                    image=image_file,
                    title=os.path.splitext(image_file.name)[0]
                )
                uploaded_count += 1
            except:
                pass

        if uploaded_count > 0:
            messages.success(request, f'Загружено {uploaded_count} изображений.')

    return redirect('index')


@login_required
def delete_image(request, image_id):
    image = get_object_or_404(UserImage, id=image_id, user=request.user)
    image.delete()
    messages.success(request, 'Изображение удалено.')
    return redirect('index')


@login_required
def result(request):
    last_request_id = request.session.get("last_resume_request_id")
    last_request = None
    resume = ""
    if last_request_id:
        try:
            last_request = ResumeRequest.objects.get(id=last_request_id, user=request.user)
            resume = last_request.resume_content
        except ResumeRequest.DoesNotExist:
            pass
    return render(request, "result.html", {"last_request": last_request, "resume": resume})


@login_required
def history(request):
    resume_requests = ResumeRequest.objects.filter(user=request.user).order_by('-created_at')
    return render(request, "history.html", {"resume_requests": resume_requests})


@login_required
def resume_detail(request, request_id):
    resume_request = get_object_or_404(ResumeRequest, id=request_id, user=request.user)
    return render(request, "resume_detail.html", {"resume_request": resume_request})


@login_required
def download_resume(request, request_id):
    resume_request = get_object_or_404(ResumeRequest, id=request_id, user=request.user)

    if resume_request.resume_file:
        # Скачиваем ZIP-архив
        return FileResponse(
            resume_request.resume_file.open('rb'),
            as_attachment=True,
            filename=f"resumes_{resume_request.user.username}_{resume_request.created_at.strftime('%Y%m%d')}.zip",
            content_type='application/zip'
        )

    # Fallback: текстовый файл
    response = HttpResponse(resume_request.resume_content, content_type='text/plain; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="resume_{request_id}.txt"'
    return response


@login_required
def view_resume_file(request, request_id):
    resume_request = get_object_or_404(ResumeRequest, id=request_id, user=request.user)
    if not resume_request.resume_file:
        raise Http404("Файл не найден")
    return FileResponse(resume_request.resume_file.open('rb'), content_type='application/zip')


@login_required
def profile(request):
    profile_obj, _ = UserProfile.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        form = UserProfileForm(request.POST, request.FILES, instance=profile_obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Профиль обновлён.")
            return redirect('profile')
    else:
        form = UserProfileForm(instance=profile_obj)

    recent_requests = ResumeRequest.objects.filter(user=request.user).order_by('-created_at')[:5]
    total_requests = ResumeRequest.objects.filter(user=request.user).count()

    return render(request, "profile.html", {
        "form": form,
        "recent_requests": recent_requests,
        "total_requests": total_requests
    })


def register_view(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            UserProfile.objects.create(user=user)
            login(request, user)
            messages.success(request, f'Добро пожаловать, {user.username}!')
            return redirect('index')
    else:
        form = CustomUserCreationForm()
    return render(request, 'auth/register.html', {'form': form})


def login_view(request):
    if request.method == 'POST':
        form = CustomAuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f'Добро пожаловать, {user.username}!')
            return redirect(request.GET.get('next', 'index'))
    else:
        form = CustomAuthenticationForm()
    return render(request, 'auth/login.html', {'form': form})


def logout_view(request):
    logout(request)
    messages.info(request, 'Вы вышли из системы.')
    return redirect('index')


def help_page(request):
    return render(request, "help.html")


def contacts(request):
    return render(request, "contacts.html")


def how_it_works(request):
    return render(request, "how_it_works.html")


def about(request):
    return render(request, "about.html")
