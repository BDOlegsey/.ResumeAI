import json
import logging
import os
from datetime import datetime

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import Http404, HttpResponse, FileResponse
from django.shortcuts import get_object_or_404, redirect, render

from .forms import (
    CustomAuthenticationForm,
    CustomUserCreationForm,
    EducationForm,
    PortfolioItemForm,
    ResumeGenerationForm,
    UserImageForm,
    UserProfileForm,
    WorkExperienceForm,
)
from .models import (
    Education,
    PortfolioItem,
    ResumeRequest,
    ResumeResult,
    UserImage,
    UserProfile,
    WorkExperience,
)
from .agents.pipeline import run_resume_pipeline
from .agents.preprocess_agent import validate_profile


logger = logging.getLogger("core")


@login_required
def profile(request):
    user_profile, _ = UserProfile.objects.get_or_create(user=request.user)
    work_experiences = (
        WorkExperience.objects.filter(user=request.user)
        .order_by("-start_date")
    )
    educations = (
        Education.objects.filter(user=request.user).order_by("-start_date")
    )
    portfolio_items = (
        PortfolioItem.objects.filter(user=request.user)
        .order_by("-created_at")
    )

    profile_form = UserProfileForm(
        request.POST or None,
        request.FILES or None,
        instance=user_profile,
    )
    work_exp_form = WorkExperienceForm(request.POST or None)
    education_form = EducationForm(request.POST or None)
    portfolio_form = PortfolioItemForm(
        request.POST or None, request.FILES or None
    )

    if request.method == "POST":
        if "profile_submit" in request.POST and profile_form.is_valid():
            user_profile = profile_form.save(user=request.user)
            logger.info("User %s updated profile", request.user.username)
            messages.success(request, "Профиль успешно обновлен!")
            return redirect("profile")

        elif "work_exp_submit" in request.POST and work_exp_form.is_valid():
            work_exp = work_exp_form.save(commit=False)
            work_exp.user = request.user
            work_exp.save()
            messages.success(request, "Опыт работы добавлен!")
            return redirect("profile")

        elif "education_submit" in request.POST and education_form.is_valid():
            education = education_form.save(commit=False)
            education.user = request.user
            education.save()
            messages.success(request, "Образование добавлено!")
            return redirect("profile")

        elif "portfolio_submit" in request.POST and portfolio_form.is_valid():
            item = portfolio_form.save(commit=False)
            item.user = request.user
            item.save()
            messages.success(request, "Проект добавлен в портфолио!")
            return redirect("profile")

    total_requests = ResumeRequest.objects.filter(user=request.user).count()

    return render(
        request,
        "profile.html",
        {
            "profile_form": profile_form,
            "work_exp_form": work_exp_form,
            "education_form": education_form,
            "portfolio_form": portfolio_form,
            "work_experiences": work_experiences,
            "educations": educations,
            "portfolio_items": portfolio_items,
            "total_requests": total_requests,
            "user_profile": user_profile,
        },
    )


@login_required
def index(request):
    if request.method == "POST":
        logger.info("Index POST: start resume generation request by user_id=%s", request.user.id)
        form = ResumeGenerationForm(request.POST, user=request.user)
        if not form.is_valid():
            messages.error(request, "Проверьте корректность формы.")
            return render(request, "index.html", {"form": form})

        # Проверка профиля агентом перед запуском пайплайна
        try:
            user_profile = request.user.profile
            validation_result = validate_profile(user_profile)
            for msg in validation_result.as_messages:
                messages.warning(request, msg)
            if validation_result.status == "block":
                messages.error(
                    request,
                    "Профиль неполный или содержит ошибки. Дополните данные и попробуйте снова.",
                )
                return render(request, "index.html", {"form": form})
        except UserProfile.DoesNotExist:
            messages.warning(
                request,
                "Профиль пользователя ещё не заполнен — это может ухудшить качество резюме.",
            )

        targets = form.parse_targets()
        extra_instructions = form.cleaned_data["extra_instructions"]
        additional_wishes = form.cleaned_data.get("additional_wishes", "")
        include_photo = form.cleaned_data.get("include_photo", False)
        strict_matching = form.cleaned_data["strict_matching"]
        add_skills = form.cleaned_data["add_skills"]
        selected_images = form.cleaned_data.get("selected_images") or []

        # Объединяем дополнительные пожелания с специфичными условиями
        # (в старой версии специфичные условия были отдельным полем, но теперь объединены)
        # specific_conditions = form.cleaned_data.get("specific_conditions", "")
        # if specific_conditions and additional_wishes:
        #     combined_info = f"{additional_wishes}\n\nСпецифичные условия: {specific_conditions}"
        # elif specific_conditions:
        #     combined_info = f"Специфичные условия: {specific_conditions}"
        # else:
        #     combined_info = additional_wishes
        # additional_wishes = combined_info

        with transaction.atomic():
            resume_request = ResumeRequest.objects.create(
                user=request.user,
                employers="\n".join(
                    [
                        t["company"]
                        + (f" — {t['role']}" if t["role"] else "")
                        for t in targets
                    ]
                ),
                achievements=extra_instructions or "",
                targets=targets,
                extra_instructions=extra_instructions,
                additional_wishes=additional_wishes,
                include_photo=include_photo,
                strict_matching=strict_matching,
                add_skills=add_skills,
                specific_conditions="",  # Поле больше не используется, но сохраняем для совместимости
                status=ResumeRequest.Status.PENDING,
            )

            if selected_images:
                image_ids = [
                    int(x) for x in selected_images if str(x).isdigit()
                ]
                images = UserImage.objects.filter(
                    id__in=image_ids, user=request.user
                )
                resume_request.images.add(*images)
                messages.info(
                    request,
                    f"Прикреплено {images.count()} изображений к запросу.",
                )

        # Запуск мультиагентного пайплайна
        try:
            resume_request.status = ResumeRequest.Status.RUNNING
            resume_request.save(update_fields=["status"])

            logger.info(
                "Invoking run_resume_pipeline for request_id=%s targets=%d include_photo=%s",
                resume_request.id,
                len(resume_request.targets or []),
                getattr(resume_request, "include_photo", False),
            )
            archive_path = run_resume_pipeline(request.user, resume_request)

            if archive_path:
                from django.core.files.base import File

                with open(archive_path, "rb") as f:
                    resume_request.archive_file.save(
                        os.path.basename(archive_path),
                        File(f),
                        save=False,
                    )

                resume_request.status = ResumeRequest.Status.DONE
                resume_request.save()
                messages.success(
                    request,
                    "Генерация резюме завершена. Доступен архив для скачивания.",
                )
            else:
                resume_request.status = ResumeRequest.Status.PARTIAL
                resume_request.save()
                messages.warning(
                    request,
                    "Генерация завершена частично: DOCX не были созданы.",
                )

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
            last_request = ResumeRequest.objects.get(
                id=last_request_id, user=request.user
            )
        except ResumeRequest.DoesNotExist:
            last_request = None

    return render(request, "result.html", {"last_request": last_request})


@login_required
def history(request):
    resume_requests = ResumeRequest.objects.filter(
        user=request.user
    ).order_by("-created_at")
    return render(request, "history.html", {"resume_requests": resume_requests})


@login_required
def resume_detail(request, request_id):
    resume_request = get_object_or_404(
        ResumeRequest, id=request_id, user=request.user
    )
    results = resume_request.results.all().order_by("-created_at")
    return render(
        request,
        "resume_detail.html",
        {"resume_request": resume_request, "results": results},
    )


@login_required
def download_archive(request, request_id):
    resume_request = get_object_or_404(
        ResumeRequest, id=request_id, user=request.user
    )
    if not resume_request.archive_file:
        raise Http404("Архив не найден")
    return FileResponse(
        resume_request.archive_file.open("rb"),
        as_attachment=True,
        filename=os.path.basename(resume_request.archive_file.name),
    )


@login_required
def view_archive_file(request, request_id):
    resume_request = get_object_or_404(
        ResumeRequest, id=request_id, user=request.user
    )
    if not resume_request.archive_file:
        raise Http404("Архив не найден")
    return FileResponse(
        resume_request.archive_file.open("rb"),
        filename=os.path.basename(resume_request.archive_file.name),
    )


@login_required
def download_result_docx(request, result_id):
    result = get_object_or_404(
        ResumeResult, id=result_id, request__user=request.user
    )
    if not result.docx_file:
        raise Http404("DOCX не найден")
    return FileResponse(
        result.docx_file.open("rb"),
        as_attachment=True,
        filename=os.path.basename(result.docx_file.name),
    )


@login_required
def download_result_json(request, result_id):
    result = get_object_or_404(
        ResumeResult, id=result_id, request__user=request.user
    )
    if not result.json_file:
        data = json.dumps(result.json_data or {}, ensure_ascii=False, indent=2)
        resp = HttpResponse(
            data, content_type="application/json; charset=utf-8"
        )
        resp[
            "Content-Disposition"
        ] = f'attachment; filename="resume_{result.id}.json"'
        return resp

    return FileResponse(
        result.json_file.open("rb"),
        as_attachment=True,
        filename=os.path.basename(result.json_file.name),
    )


@login_required
def upload_images(request):
    if request.method == "POST" and request.FILES:
        images = request.FILES.getlist("images")
        if not images:
            messages.error(request, "Пожалуйста, выберите файлы для загрузки.")
            return redirect("index")

        uploaded_count, errors = 0, []
        for image_file in images:
            try:
                if image_file.size > getattr(
                    settings, "MAX_UPLOAD_SIZE", 5 * 1024 * 1024
                ):
                    errors.append(
                        f"Файл {image_file.name} слишком большой (макс. 5MB)"
                    )
                    continue

                ext = os.path.splitext(image_file.name)[1].lower().lstrip(".")
                allowed = getattr(
                    settings,
                    "ALLOWED_IMAGE_EXTENSIONS",
                    {"jpg", "jpeg", "png", "gif", "bmp"},
                )
                if ext not in allowed:
                    errors.append(
                        f"Файл {image_file.name} должен быть изображением (JPG, PNG, GIF, BMP)"
                    )
                    continue

                try:
                    from PIL import Image

                    img = Image.open(image_file)
                    img.verify()
                    image_file.seek(0)
                except Exception:
                    errors.append(
                        f"Файл {image_file.name} не является корректным изображением"
                    )
                    continue

                UserImage.objects.create(
                    user=request.user,
                    image=image_file,
                    title=os.path.splitext(image_file.name)[0],
                )
                uploaded_count += 1
            except Exception as e:
                errors.append(
                    f"Ошибка при загрузке {image_file.name}: {str(e)}"
                )

        if uploaded_count > 0:
            messages.success(
                request, f"Успешно загружено {uploaded_count} изображений."
            )
        for error in errors:
            messages.error(request, error)

        return redirect("index")

    return redirect("index")


@login_required
def delete_image(request, image_id):
    image = get_object_or_404(UserImage, id=image_id, user=request.user)
    title = image.title or "Изображение"
    image.delete()
    messages.success(request, f'Изображение "{title}" удалено.')
    return redirect("index")


@login_required
def delete_work_experience(request, experience_id):
    experience = get_object_or_404(
        WorkExperience, id=experience_id, user=request.user
    )
    experience.delete()
    messages.success(request, "Опыт работы удален!")
    return redirect("profile")


@login_required
def delete_education(request, education_id):
    education = get_object_or_404(
        Education, id=education_id, user=request.user
    )
    education.delete()
    messages.success(request, "Образование удалено!")
    return redirect("profile")


@login_required
def delete_portfolio_item(request, item_id):
    item = get_object_or_404(
        PortfolioItem, id=item_id, user=request.user
    )
    item.delete()
    messages.success(request, "Проект удален из портфолио!")
    return redirect("profile")


def register_view(request):
    if request.method == "POST":
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            UserProfile.objects.create(user=user)
            login(request, user)
            messages.success(
                request,
                f"Добро пожаловать, {user.username}! Вы успешно зарегистрировались.",
            )
            return redirect("index")
    else:
        form = CustomUserCreationForm()

    return render(request, "auth/register.html", {"form": form})


def login_view(request):
    if request.method == "POST":
        form = CustomAuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get("username")
            password = form.cleaned_data.get("password")
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, f"Добро пожаловать, {username}!")
                next_url = request.GET.get("next", "index")
                return redirect(next_url)
    else:
        form = CustomAuthenticationForm()

    return render(request, "auth/login.html", {"form": form})


def logout_view(request):
    logout(request)
    messages.info(request, "Вы успешно вышли из системы.")
    return redirect("index")


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
    experience = get_object_or_404(
        WorkExperience, id=experience_id, user=request.user
    )
    if request.method == "POST":
        form = WorkExperienceForm(request.POST, instance=experience)
        if form.is_valid():
            form.save()
            messages.success(request, "Опыт работы успешно обновлен!")
            return redirect("profile")
    else:
        form = WorkExperienceForm(instance=experience)

    return render(
        request,
        "edit_work_experience.html",
        {"form": form, "experience": experience},
    )


@login_required
def edit_education(request, education_id):
    education = get_object_or_404(
        Education, id=education_id, user=request.user
    )
    if request.method == "POST":
        form = EducationForm(request.POST, instance=education)
        if form.is_valid():
            form.save()
            messages.success(request, "Образование успешно обновлено!")
            return redirect("profile")
    else:
        form = EducationForm(instance=education)

    return render(
        request,
        "edit_education.html",
        {"form": form, "education": education},
    )


@login_required
def edit_portfolio_item(request, item_id):
    item = get_object_or_404(
        PortfolioItem, id=item_id, user=request.user
    )
    if request.method == "POST":
        form = PortfolioItemForm(
            request.POST, request.FILES, instance=item
        )
        if form.is_valid():
            form.save()
            messages.success(request, "Проект успешно обновлен!")
            return redirect("profile")
    else:
        form = PortfolioItemForm(instance=item)

    return render(
        request,
        "edit_portfolio_item.html",
        {"form": form, "item": item},
    )
