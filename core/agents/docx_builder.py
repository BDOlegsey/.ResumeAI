import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Dict, Any, Optional

from django.conf import settings
from docx.shared import Mm
from docxtpl import DocxTemplate, InlineImage
from jsonschema import validate as jsonschema_validate, ValidationError
from PIL import Image, UnidentifiedImageError

logger = logging.getLogger("resume_ai")

SCHEMA_PATH = Path(settings.BASE_DIR) / "schema.json"
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff"}


def _ensure_parent_dir(path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)


def _load_schema() -> Dict[str, Any]:
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _get_template_path() -> str:
    tpl = getattr(settings, "DOCX_TEMPLATE_PATH", None) or os.path.join(
        settings.BASE_DIR, "template.docx"
    )
    if not os.path.exists(tpl):
        logger.error("DOCX template not found: %s", tpl)
        raise FileNotFoundError(f"Не найден шаблон DOCX: {tpl}")
    return tpl


def _tmp_dir() -> Path:
    p = Path(
        getattr(
            settings,
            "DOCX_INLINE_TMP_DIR",
            Path(settings.MEDIA_ROOT) / "tmp" / "inline_images",
        )
    )
    p.mkdir(parents=True, exist_ok=True)
    return p


def _to_png_temp(src_path: Path) -> Optional[Path]:
    """
    Открывает источник через PIL и сохраняет его в PNG в tmp,
    чтобы python-docx всегда принял файл как валидное изображение.
    """
    try:
        with Image.open(str(src_path)) as im:
            im.load()  # прогрузить для некоторых форматов
            # Конвертируем режим для совместимости
            if im.mode in ("P", "LA", "RGBA"):
                im = im.convert("RGB")

            # Хеш пути + времени модификации для уникального имени
            h = hashlib.sha1(
                f"{src_path.resolve()}|{src_path.stat().st_mtime}".encode("utf-8")
            ).hexdigest()[:16]
            out_path = _tmp_dir() / f"img_{h}.png"
            im.save(str(out_path), format="PNG", optimize=True)
            return out_path
    except (UnidentifiedImageError, OSError) as exc:
        logger.warning(
            "Невозможно открыть изображение для конвертации: %s (%s)", src_path, exc
        )
        return None
    except Exception as exc:
        logger.exception("Ошибка при конвертации изображения в PNG: %s", exc)
        return None


def _maybe_inline_photo(
    doc: DocxTemplate, photo_path: Optional[str]
) -> Optional[InlineImage]:
    """
    Валидирует и конвертирует изображение в PNG для безопасной вставки через InlineImage.
    """
    if not photo_path:
        return None

    src = Path(photo_path)
    if not src.exists() or not src.is_file():
        return None

    # Попытка через расширение
    if src.suffix.lower() not in ALLOWED_IMAGE_EXTENSIONS:
        png_path = _to_png_temp(src)
        if not png_path:
            return None
        width_mm = float(getattr(settings, "PROFILE_PHOTO_WIDTH_MM", 26))
        return InlineImage(doc, str(png_path), width=Mm(width_mm))

    # Попытка открыть + конвертировать в PNG (универсальный формат для python-docx)
    png_path = _to_png_temp(src)
    if not png_path:
        return None

    width_mm = float(getattr(settings, "PROFILE_PHOTO_WIDTH_MM", 26))
    return InlineImage(doc, str(png_path), width=Mm(width_mm))


def render_docx(
    json_data: Dict[str, Any],
    out_path: str,
    photo_path: Optional[str] = None,
) -> str:
    """
    Рендер DOCX:

    1) валидация JSON по schema.json;
    2) наполнение docxtpl‑шаблона;
    3) опциональная вставка фотографии.
    """
    logger.info("Rendering DOCX to %s", out_path)

    # 1) Валидация JSON по схеме
    schema = _load_schema()
    try:
        jsonschema_validate(instance=json_data, schema=schema)
    except ValidationError as exc:
        path_str = " -> ".join(map(str, list(exc.path)))
        msg = f"Ошибка валидации JSON для DOCX: {exc.message} (путь: {path_str})"
        logger.error(msg)
        raise ValueError(msg)

    # 2) Рендер docxtpl
    tpl_path = _get_template_path()
    doc = DocxTemplate(tpl_path)

    ctx: Dict[str, Any] = {**json_data}
    inline = _maybe_inline_photo(doc, photo_path)
    if inline is not None:
        ctx["photo"] = inline

    _ensure_parent_dir(out_path)
    doc.render(ctx)
    doc.save(out_path)

    logger.info("DOCX successfully saved to %s", out_path)
    return out_path
