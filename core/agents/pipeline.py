import json
import logging
import os
import zipfile
from typing import Dict, Any, List, Optional

from django.conf import settings
from django.core.files.base import File

from .graph import build_resume_graph
from .docx_builder import render_docx
from .schemas import validate_json_payload
from .preprocess_agent import validate_profile  # сейчас используется во views, можно оставить импорт
from ..models import ResumeResult

logger = logging.getLogger("resume_ai")


def _configure_logger() -> None:
    """
    Локальная конфигурация логгера для записи в файл resume_ai.log, если хендлеры ещё не настроены.
    """
    if logger.handlers:
        return
    try:
        log_dir = os.path.join(settings.BASE_DIR, "logs")
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(log_dir, "resume_ai.log")
        fh = logging.FileHandler(log_path, encoding="utf-8")
        fmt = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        )
        fh.setFormatter(fmt)
        logger.addHandler(fh)
        logger.setLevel(logging.INFO)
    except Exception:
        logging.basicConfig(level=logging.INFO)


_configure_logger()


def _ensure_dir(path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)


def _profile_to_dict(profile) -> Dict[str, Any]:
    """
    Сериализация профиля пользователя и связанных сущностей
    в компактный словарь для генератора.
    """
    user = profile.user

    work = [
        {
            "company": w.company,
            "position": w.position,
            "start_date": w.start_date.isoformat() if w.start_date else "",
            "end_date": w.end_date.isoformat() if w.end_date else "",
            "currently_working": w.currently_working,
            "description": w.description or "",
        }
        for w in user.work_experiences.all().order_by("-start_date")
    ]

    edu = [
        {
            "institution": e.institution,
            "degree": e.degree,
            "specialty": e.specialty,
            "start_date": e.start_date.isoformat() if e.start_date else "",
            "end_date": e.end_date.isoformat() if e.end_date else "",
            "currently_studying": e.currently_studying,
            "description": e.description or "",
        }
        for e in user.educations.all().order_by("-start_date")
    ]

    return {
        "user_id": user.id,
        "full_name": profile.full_name,
        "gender": profile.gender,
        "birth_date": profile.birth_date.isoformat()
        if profile.birth_date
        else "",
        "phone": profile.phone,
        "email": profile.email or user.email,
        "location": profile.address,
        "citizenship": profile.citizenship,
        "profession": profile.profession,
        "skills": [
            s.strip() for s in (profile.skills or "").split(",") if s.strip()
        ],
        "additional_info": profile.additional_info or "",
        "work_experience": work,
        "education": edu,
        "portfolio": [
            {
                "title": p.title,
                "description": p.description,
                "link": p.link,
            }
            for p in user.portfolio_items.all().order_by("-created_at")
        ],
    }


def _controls_from_request(rr) -> Dict[str, Any]:
    return {
        "strict_matching": rr.strict_matching,
        "add_skills": rr.add_skills,
        "specific_conditions": rr.specific_conditions,
        "extra_instructions": rr.extra_instructions,
        "additional_wishes": rr.additional_wishes,
        "include_photo": rr.include_photo,
    }


def _save_json_file(base_dir: str, company_slug: str, data: Dict[str, Any]) -> str:
    path = os.path.join(base_dir, f"{company_slug}.json")
    _ensure_dir(path)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return path


def _slug(name: str) -> str:
    import re

    s = (name or "company").strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-") or "company"


def _select_photo_path(resume_request, profile) -> Optional[str]:
    """
    Приоритет: 1) прикреплённое к запросу изображение, 2) фото профиля пользователя.
    """
    if not getattr(resume_request, "include_photo", False):
        return None
    # 1. Попытка взять прикреплённые к запросу изображения
    try:
        first_image = resume_request.images.first()
        if (
            first_image
            and hasattr(first_image, "image")
            and getattr(first_image.image, "path", None)
        ):
            if os.path.exists(first_image.image.path):
                return first_image.image.path
    except Exception as exc:
        logger.warning("Failed to select image from request: %s", exc)

    # 2. Фото профиля пользователя
    try:
        if (
            profile.photo
            and getattr(profile.photo, "path", None)
            and os.path.exists(profile.photo.path)
        ):
            return profile.photo.path
    except Exception as exc:
        logger.warning("Failed to select profile photo: %s", exc)

    return None


def run_resume_pipeline(user, resume_request) -> str:
    """
    Выполняет граф LangGraph для каждой цели, сохраняет JSON, генерирует DOCX (если проверка пройдена),
    и собирает ZIP из успешно проверенных файлов DOCX; возвращает путь к ZIP [в media] для сохранения во views.
    """
    logger.info(
        "Run resume pipeline for user_id=%s request_id=%s targets=%d include_photo=%s",
        user.id,
        resume_request.id,
        len(resume_request.targets or []),
        getattr(resume_request, "include_photo", False),
    )

    max_regens = int(getattr(settings, "MAX_REGEN_ATTEMPTS", 1))
    graph = build_resume_graph(max_regens=max_regens)
    profile = user.profile
    user_profile_dict = _profile_to_dict(profile)
    controls = _controls_from_request(resume_request)

    media_root = settings.MEDIA_ROOT
    date_dir = os.path.join(
        media_root,
        "resumes",
        f"user_{user.id}",
        resume_request.created_at.strftime("%Y/%m/%d"),
        f"req_{resume_request.id}",
    )
    os.makedirs(date_dir, exist_ok=True)

    created_docx_paths: List[str] = []
    partial = False

    photo_path: Optional[str] = _select_photo_path(resume_request, profile)
    logger.info(
        "Selected photo_path for request %s: %s",
        resume_request.id,
        photo_path,
    )

    for target in (resume_request.targets or []):
        company = target.get("company") or ""
        role = target.get("role") or ""
        job_url = target.get("url") or ""
        slug = _slug(company or role or "company")

        logger.info(
            "Invoking graph for target company=%s role=%s url_present=%s",
            company or "",
            role or "",
            bool(job_url),
        )

        initial_state = {
            "user_profile": user_profile_dict,
            "target": target,
            "request_controls": controls,
            "plan": {},
            "search_data": {},
            "generated": {},
            "approved": False,
            "errors": [],
            "retries": 0,
            "regen_directives": {},
        }

        try:
            state = graph.invoke(initial_state)
        except Exception as exc:
            logger.exception(
                "Graph invocation failed for company=%s role=%s: %s",
                company or "",
                role or "",
                exc,
            )
            state = {
                "generated": {},
                "approved": False,
                "errors": [f"Graph error: {exc}"],
            }

        generated = state.get("generated") or {}

        # Дополнительный фолбэк для full_name на уровне пайплайна
        if not generated.get("full_name"):
            generated["full_name"] = user_profile_dict.get("full_name", "") or ""

        schema_errors = validate_json_payload(generated)
        approved = state.get("approved", False) and not schema_errors

        notes = "\n".join(state.get("errors") or [])
        if schema_errors:
            notes = (notes + "\n" if notes else "") + "\n".join(schema_errors)

        result = ResumeResult.objects.create(
            request=resume_request,
            company=company or (generated.get("company") or "Компания"),
            role=role or (generated.get("desired_position") or ""),
            job_url=job_url,
            json_data=generated,
            approved=approved,
            notes=(notes or "").strip(),
        )

        json_path = _save_json_file(os.path.join(date_dir, "json"), slug, generated)
        with open(json_path, "rb") as jf:
            result.json_file.save(os.path.basename(json_path), File(jf), save=True)

        if approved:
            docx_dir = os.path.join(date_dir, "docx")
            os.makedirs(docx_dir, exist_ok=True)

            from datetime import datetime as dt

            base_name = (company or role or "resume").strip().replace(" ", "_")
            docx_filename = f"{base_name}_{dt.now().strftime('%Y%m%d_%H%M%S')}.docx"
            docx_path = os.path.join(docx_dir, docx_filename)

            try:
                render_docx(generated, docx_path, photo_path=photo_path)
                with open(docx_path, "rb") as df:
                    result.docx_file.save(
                        os.path.basename(docx_path), File(df), save=True
                    )
                created_docx_paths.append(docx_path)
                logger.info(
                    "DOCX generated for company=%s, path=%s",
                    company or "",
                    docx_path,
                )
            except Exception as exc:
                logger.exception(
                    "DOCX rendering failed for company=%s: %s",
                    company or "",
                    exc,
                )
                partial = True
        else:
            partial = True

    # Если нет ни одного DOCX — ZIP не создаём
    if not created_docx_paths:
        if partial:
            logger.warning(
                "Pipeline finished with partial results, but no DOCX files created."
            )
        else:
            logger.warning("Pipeline finished, but no targets were processed.")
        return ""

    zip_dir = os.path.join(date_dir, "zip")
    os.makedirs(zip_dir, exist_ok=True)
    from datetime import datetime as dt

    zip_filename = f"resumes_{dt.now().strftime('%Y%m%d_%H%M%S')}.zip"
    zip_path = os.path.join(zip_dir, zip_filename)

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in created_docx_paths:
            arcname = os.path.basename(path)
            zf.write(path, arcname)

    logger.info(
        "ZIP archive created for request_id=%s: %s",
        resume_request.id,
        zip_path,
    )
    return zip_path
