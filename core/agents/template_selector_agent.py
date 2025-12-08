"""
Агент выбора шаблона резюме
"""
import logging
from typing import Dict, Any
from .templates import get_available_templates, get_template_schema
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from .system_prompts import SYSTEM_INSTRUCTIONS_TEMPLATE_SELECTOR

logger = logging.getLogger('core.agents')

def select_template(user_profile: Dict[str, Any], target: Dict[str, Any], request_controls: Dict[str, Any]) -> Dict[str, Any]:
    """
    Выбор подходящего шаблона резюме на основе профиля пользователя, цели и контрольных параметров
    """
    # Получаем список доступных шаблонов
    available_templates = get_available_templates()
    
    # Определяем целевую страну или формат
    target_country = request_controls.get('target_country', 'russian')
    target_format = request_controls.get('target_format', 'russian')
    
    # Проверяем, есть ли указанный формат в доступных
    if target_format in available_templates:
        selected_template = target_format
    elif target_country in available_templates:
        selected_template = target_country
    else:
        # По умолчанию используем российский формат
        selected_template = 'russian'
    
    # Получаем схему для выбранного шаблона
    template_schema = get_template_schema(selected_template)
    
    result = {
        "template_name": selected_template,
        "template_title": available_templates[selected_template],
        "template_schema": template_schema,
        "selected_for": {
            "target_company": target.get('company'),
            "target_role": target.get('role'),
            "target_country": target_country,
            "target_format": target_format
        }
    }
    
    logger.info(f"Template selected: {selected_template} for company={target.get('company')}, role={target.get('role')}")
    return result

SYSTEM_INSTRUCTIONS_TEMPLATE_SELECTOR = '''
Ты - агент выбора шаблона резюме в мультиагентной системе. Твоя задача - выбрать наиболее подходящий формат резюме на основе профиля пользователя, целей поиска работы и требований работодателя.

**Инструкции:**
1. Получи от пользователя данные профиля:
   - Личная информация: ФИО, пол, дата рождения, контакты, местоположение
   - Опыт работы: компании, должности, периоды, обязанности, достижения
   - Образование: вузы, годы, факультеты, программы
   - Навыки: hard skills, soft skills, языки, водительские права
   - Дополнительная информация: портфолио, рекомендации, "обо мне"

2. Получи от пользователя цели:
   - Целевая компания/работодатель
   - Целевая должность
   - Целевая страна/рынок труда
   - Предпочтения по формату резюме (если есть)

3. Получи контрольные параметры:
   - Целевая страна (target_country)
   - Целевой формат (target_format)
   - Дополнительные требования к формату

4. Выбери наиболее подходящий шаблон резюме из доступных:
   - europass: Европейский стандарт резюме
   - ats_optimized: Резюме, оптимизированное для систем отслеживания кандидатов
   - chronological: Классическое хронологическое резюме
   - functional: Функциональное резюме
   - combination: Комбинированное резюме
   - russian: Российский формат резюме
   - us: Американский формат резюме
   - uk: Британский формат резюме
   - german: Немецкий формат резюме (Lebenslauf)
   - french: Французский формат резюме
   - chinese: Китайский формат резюме
   - japanese: Японский формат резюме (Rirekisho)

5. Сгенерируй JSON с информацией о выбранном шаблоне:
{
  "template_name": "ключ_шаблона",
  "template_title": "Название шаблона",
  "template_schema": {схема_для_валидации},
  "selected_for": {
    "target_company": "название_компании",
    "target_role": "название_должности",
    "target_country": "страна",
    "target_format": "формат"
  }
}

**Правила выбора шаблона:**
- Для международных компаний используй Europass или ATS-оптимизированный формат
- Для российских компаний используй российский формат
- Для американских компаний используй US формат
- Для британских компаний используй UK формат
- Для немецких компаний используй German формат (Lebenslauf)
- Для французских компаний используй French формат
- Для китайских компаний используй Chinese формат
- Для японских компаний используй Japanese формат (Rirekisho)
- При неопределенности используй хронологический формат

**Критически важно:**
- Выбирай формат, который соответствует требованиям целевой страны/компании
- Учитывай специфику целевой должности (техническая, управленческая, творческая)
- Схема выбранного шаблона будет использоваться для валидации сгенерированного резюме
- Обеспечь максимальную совместимость данных профиля с выбранным форматом
'''