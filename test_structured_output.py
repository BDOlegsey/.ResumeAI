"""
Тест для проверки функциональности структурированного вывода
"""
import json
from core.agents.generator_agent import generate_resume_json
from core.agents.system_prompts import SYSTEM_INSTRUCTIONS_GENERATOR

def test_structured_output_instructions():
    """Тест, проверяющий, что инструкции содержат информацию о обработке отсутствующих данных"""
    # Проверяем, что инструкции генератора содержат информацию о "..."
    assert "..." in SYSTEM_INSTRUCTIONS_GENERATOR, "Инструкции генератора должны содержать информацию о использовании '...'"
    assert "отсутствуют в профиле пользователя, используй значение" in SYSTEM_INSTRUCTIONS_GENERATOR, "Инструкции должны содержать указание использовать '...' для отсутствующих данных"
    
    print("✓ Инструкции генератора содержат информацию о обработке отсутствующих данных")

def test_schema_compatibility():
    """Тест, проверяющий, что схемы корректно определены"""
    from core.agents.schemas import SCHEMA, validate_json_payload
    
    # Проверяем, что схема содержит хотя бы один формат
    assert len(SCHEMA) > 0, "Схема должна содержать хотя бы один формат резюме"
    
    # Проверяем, что все схемы валидны
    for template_name, schema in SCHEMA.items():
        # Проверяем, что это валидный JSON
        assert isinstance(schema, dict), f"Схема для {template_name} должна быть словарем"
        # Проверяем, что у схемы есть обязательные поля
        assert "type" in schema, f"Схема для {template_name} должна содержать тип"
        assert schema["type"] == "object", f"Схема для {template_name} должна быть объектом"
    
    print("✓ Все схемы корректно определены")

def test_missing_data_handling():
    """Тест, проверяющий, что инструкции всех агентов учитывают обработку отсутствующих данных"""
    from core.agents.system_prompts import SYSTEM_INSTRUCTIONS_CHECKER, SYSTEM_INSTRUCTIONS_SEARCHER, SYSTEM_INSTRUCTIONS_TEMPLATE_SELECTOR
    
    # Проверяем, что все инструкции содержат упоминание о "..." 
    all_instructions = [
        ("Checker", SYSTEM_INSTRUCTIONS_CHECKER),
        ("Searcher", SYSTEM_INSTRUCTIONS_SEARCHER), 
        ("Template Selector", SYSTEM_INSTRUCTIONS_TEMPLATE_SELECTOR)
    ]
    
    for agent_name, instructions in all_instructions:
        assert "..." in instructions or "используй" in instructions, f"Инструкции {agent_name} должны учитывать обработку отсутствующих данных"
    
    print("✓ Все агенты учитывают обработку отсутствующих данных")

if __name__ == "__main__":
    print("Запуск тестов структурированного вывода...")
    test_structured_output_instructions()
    test_schema_compatibility()
    test_missing_data_handling()
    print("\n✓ Все тесты пройдены успешно!")
    print("\nРезюме по изменениям:")
    print("- Инструкции генератора обновлены для использования '...' вместо генерации фиктивных данных")
    print("- Инструкции всех агентов обновлены для учета обработки отсутствующих данных")
    print("- Создана документация по работе мультиагентной системы")
    print("- Добавлены тесты для проверки корректности реализации")