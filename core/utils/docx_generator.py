from docx import Document
from docx.shared import Inches, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
import os
from datetime import datetime
from django.conf import settings
from PIL import Image as PILImage
import io


class ResumeDOCXGenerator:
    def __init__(self):
        self.doc = Document()
        self.setup_document()

    def setup_document(self):
        # Set document properties
        self.doc.core_properties.title = "Professional Resume"
        self.doc.core_properties.author = "ResumeAI"
        self.doc.core_properties.subject = "Automatically generated resume"

        # Set default font
        style = self.doc.styles['Normal']
        font = style.font
        font.name = 'Arial'
        font.size = Pt(11)

    def add_heading(self, text, level=1):
        heading = self.doc.add_heading(text, level=level)
        return heading

    def add_paragraph(self, text, style='Normal'):
        paragraph = self.doc.add_paragraph(text, style=style)
        return paragraph

    def add_bullet_points(self, items):
        for item in items:
            paragraph = self.doc.add_paragraph(style='List Bullet')
            paragraph.add_run(item)

    def add_section_header(self, text):
        paragraph = self.doc.add_paragraph()
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = paragraph.add_run(text)
        run.bold = True
        run.font.size = Pt(14)
        self.doc.add_paragraph()  # Add empty paragraph for spacing

    def add_image(self, image_path, width=Inches(4.0)):
        """Добавляет изображение в документ"""
        try:
            # Проверяем существование файла
            if not os.path.exists(image_path):
                print(f"Image file not found: {image_path}")
                return False

            # Добавляем изображение
            paragraph = self.doc.add_paragraph()
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = paragraph.add_run()
            run.add_picture(image_path, width=width)
            self.doc.add_paragraph()  # Добавляем пустой абзац для отступа
            return True

        except Exception as e:
            print(f"Error adding image {image_path}: {e}")
            return False

    def add_images_section(self, images_data):
        """Добавляет раздел с изображениями"""
        if not images_data:
            return

        self.add_section_header('ПРИКРЕПЛЕННЫЕ ИЗОБРАЖЕНИЯ')

        for image_info in images_data:
            image_path = image_info.get('path')
            image_title = image_info.get('title', 'Изображение')

            # Добавляем название изображения
            title_paragraph = self.doc.add_paragraph()
            title_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            title_run = title_paragraph.add_run(image_title)
            title_run.bold = True

            # Добавляем само изображение
            self.add_image(image_path)

            # Добавляем разделитель между изображениями
            self.doc.add_paragraph()

    def generate_resume_docx(self, resume_data, user_data, images_data=None, output_path=None):
        """
        Generate DOCX resume from data

        Args:
            resume_data: Dict with resume content
            user_data: Dict with user information
            images_data: List of dicts with image paths and titles
            output_path: Path to save the DOCX file
        """
        try:
            # Title
            title = self.add_heading('ПРОФЕССИОНАЛЬНОЕ РЕЗЮМЕ', 0)
            title.alignment = WD_ALIGN_PARAGRAPH.CENTER

            # Personal Information
            self.add_section_header('ЛИЧНАЯ ИНФОРМАЦИЯ')
            personal_info = [
                f"ФИО: {user_data.get('username', 'Не указано')}",
                f"Профессия: {user_data.get('profession', 'Не указана')}",
                f"Телефон: {user_data.get('phone', 'Не указан')}",
                f"Email: {user_data.get('email', 'Не указан')}",
                f"Дата создания: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
            ]
            self.add_bullet_points(personal_info)

            # Career Objective
            if resume_data.get('employers'):
                self.add_section_header('ЦЕЛЬ КАРЬЕРЫ')
                self.add_paragraph(resume_data['employers'])

            # Professional Experience
            if resume_data.get('achievements'):
                self.add_section_header('ПРОФЕССИОНАЛЬНЫЙ ОПЫТ И НАВЫКИ')

                # Split achievements by lines or bullets
                achievements = resume_data['achievements'].split('\n')
                achievements = [ach.strip() for ach in achievements if ach.strip()]
                self.add_bullet_points(achievements)

            # Добавляем изображения если они есть
            if images_data:
                self.add_images_section(images_data)

            # Generated Resume Content
            if resume_data.get('resume_content'):
                self.add_section_header('СГЕНЕРИРОВАННОЕ РЕЗЮМЕ')

                # Split content into paragraphs
                content_paragraphs = resume_data['resume_content'].split('\n\n')
                for paragraph in content_paragraphs:
                    if paragraph.strip():
                        self.add_paragraph(paragraph.strip())

            # Footer
            self.doc.add_page_break()
            footer_para = self.doc.add_paragraph()
            footer_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
            footer_run = footer_para.add_run('Сгенерировано автоматически с помощью ResumeAI')
            footer_run.italic = True
            footer_run.font.size = Pt(9)

            # Ensure directory exists
            if output_path:
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                # Save document
                self.doc.save(output_path)
                return True
            else:
                # Return document object if no output path
                return self.doc

        except Exception as e:
            print(f"Error generating DOCX: {e}")
            return False


def create_resume_docx(resume_request, user_profile=None):
    """
    Create DOCX file for resume request
    """
    # Prepare data
    resume_data = {
        'employers': resume_request.employers,
        'achievements': resume_request.achievements,
        'resume_content': resume_request.resume_content
    }

    user_data = {
        'username': resume_request.user.username,
        'email': resume_request.user.email,
        'profession': user_profile.profession if user_profile else '',
        'phone': user_profile.phone if user_profile else ''
    }

    # Prepare images data
    images_data = []
    if resume_request.images.exists():
        for user_image in resume_request.images.all():
            if user_image.image and os.path.exists(user_image.image.path):
                images_data.append({
                    'path': user_image.image.path,
                    'title': user_image.title or 'Изображение'
                })

    # Generate filename
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"resume_{resume_request.user.username}_{timestamp}.docx"
    file_path = os.path.join(settings.MEDIA_ROOT, 'resumes', f'user_{resume_request.user.id}', filename)

    # Generate DOCX
    generator = ResumeDOCXGenerator()
    success = generator.generate_resume_docx(resume_data, user_data, images_data, file_path)

    if success:
        # Save file path to model
        relative_path = file_path.replace(settings.MEDIA_ROOT, '').lstrip('/')
        resume_request.resume_file.name = relative_path
        resume_request.save()

        # Добавляем информацию о изображениях в лог
        if images_data:
            print(f"Added {len(images_data)} images to DOCX")

        return file_path

    return None