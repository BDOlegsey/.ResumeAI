"""
Пример использования системы генерации резюме с международными форматами
"""
import os
import django
from django.conf import settings

# Установить модуль настроек Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'resume_agent.settings')
django.setup()

from core.agents.graph import build_resume_graph

def main():
    # Создаем граф
    graph = build_resume_graph()

    # Пример данных профиля пользователя
    user_profile = {
        "full_name": "Иванов Иван Иванович",
        "gender": "мужской",
        "age": 30,
        "birth_date": "01.01.1994",
        "phone": "+79991234567",
        "email": "ivanov@example.com",
        "location": "Москва",
        "citizenship": "Россия",
        "work_permit": "Да",
        "relocation_status": "Не готов к переезду",
        "travel_readiness": "Иногда",
        "desired_position": "Разработчик Python",
        "salary": "250 000 руб. на руки",
        "specializations": ["Python", "Backend", "Django"],
        "employment_type": "Полная занятость",
        "schedules": ["Полный день"],
        "commute_time": "не более 1 часа",
        "total_experience": "5 лет",
        "experience": [
            {
                "period": "01.2020 - настоящее время",
                "company": "ООО Крутая компания",
                "location": "Москва",
                "industry": "IT",
                "position": "Старший разработчик Python",
                "duties": ["Разработка backend приложений", "Работа с Django и FastAPI"],
                "achievements": ["Увеличил производительность на 30%", "Оптимизировал базы данных"]
            }
        ],
        "education": [
            {
                "year": "2015-2019",
                "university": "МГУ",
                "degree": "Бакалавр",
                "faculty": "Факультет вычислительной математики и кибернетики",
                "program": "Прикладная математика и информатика"
            }
        ],
        "languages": [
            {
                "name": "Русский",
                "level": "Родной"
            },
            {
                "name": "Английский",
                "level": "B2"
            }
        ],
        "skills": ["Python", "Django", "FastAPI", "PostgreSQL", "Docker", "Git"],
        "driving": "Категория B, стаж 5 лет",
        "references": [
            {
                "name": "Петров Петр Петрович",
                "position": "Руководитель разработки",
                "company": "ООО Крутая компания"
            }
        ],
        "about": "Опытный Python-разработчик с 5-летним стажем. Специализируюсь на backend-разработке, хорошо разбираюсь в Django, FastAPI, PostgreSQL и других технологиях."
    }

    # Цель - компания и должность
    target = {
        "company": "Google",
        "role": "Senior Software Engineer"
    }

    # Контрольные параметры - указываем целевой формат
    request_controls = {
        "target_country": "us",  # Целевая страна - США
        "target_format": "us"    # Целевой формат - американский резюме
    }

    # Запускаем генерацию
    result = graph.invoke({
        "user_profile": user_profile,
        "target": target,
        "request_controls": request_controls
    })

    print("Результат генерации:")
    print(f"Статус: {'Успешно' if result.get('approved', False) else 'Ошибка'}")
    print(f"Сгенерированное резюме: {result.get('generated', {})}")
    print(f"Ошибки: {result.get('errors', [])}")
    print(f"Выбранный шаблон: {result.get('template_info', {}).get('template_name', 'неизвестен')}")
    print(f"Попыток генерации: {result.get('retries', 0)}")

if __name__ == "__main__":
    main()