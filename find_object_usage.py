#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для поиска и подсчета использования объектов в проекте 1С
"""

import os
import re
import csv
from pathlib import Path
from typing import List, Dict, Set

def get_object_names_from_xml_files(root_path: str) -> Dict[str, Path]:
    """
    Находит все XML файлы в каталогах первого уровня и извлекает имена объектов.
    Возвращает словарь: имя_объекта -> путь_к_XML_файлу
    """
    object_name_to_path: Dict[str, Path] = {}
    root_path = Path(root_path)
    
    # Проходим по всем каталогам первого уровня
    for first_level_dir in root_path.iterdir():
        if not first_level_dir.is_dir():
            continue
            
        # Ищем XML файлы в каталогах первого уровня
        for xml_file in first_level_dir.glob("*.xml"):
            # Извлекаем имя файла без расширения
            object_name = xml_file.stem
            object_name_to_path[object_name] = xml_file
    
    return object_name_to_path

def should_skip_directory(dir_path: Path) -> bool:
    """
    Проверяет, нужно ли пропустить директорию
    """
    dir_name = dir_path.name.lower()
    return dir_name in ['.git', 'refactoring1c', '__pycache__']

def search_object_in_file(file_path: Path, object_name: str) -> int:
    """
    Ищет объект в файле и возвращает количество вхождений
    """
    try:
        # Определяем способ открытия файла в зависимости от расширения
        if file_path.name == 'Form.bin':
            # Для Form.bin файлов используем специальный режим
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        else:
            # Для остальных файлов используем обычное чтение
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        
        # Ищем все вхождения объекта (с учетом возможных префиксов/суффиксов)
        # Используем регулярное выражение для поиска объекта в контексте 1С
        pattern = rf'\b{re.escape(object_name)}\b'
        matches = re.findall(pattern, content, re.IGNORECASE)
        
        return len(matches)
        
    except Exception as e:
        print(f"Ошибка при чтении файла {file_path}: {e}")
        return 0

def count_object_usage(root_path: str, object_names: List[str]) -> Dict[str, int]:
    """
    Подсчитывает использование каждого объекта в проекте (оптимизированная версия)
    """
    usage_counts = {}
    root_path = Path(root_path)
    
    # Сначала собираем все файлы для поиска (оптимизация)
    print("Сбор файлов для поиска...")
    files_to_search = []
    
    # Поддерживаемые расширения файлов
    supported_extensions = {'.os', '.xml', '.bsl'}
    
    for file_path in root_path.rglob("*"):
        # Пропускаем директории
        if file_path.is_dir():
            continue
            
        # Пропускаем файлы в исключаемых директориях
        if any(should_skip_directory(parent) for parent in file_path.parents):
            continue
            
        # Проверяем расширение файла
        if file_path.suffix.lower() in supported_extensions:
            files_to_search.append(file_path)
        elif file_path.name == 'Form.bin':
            files_to_search.append(file_path)
    
    print(f"Найдено файлов для поиска: {len(files_to_search)}")
    
    # Создаем общий индекс всех объектов для быстрого поиска
    print("Создание индекса для быстрого поиска...")
    all_content = ""
    
    for i, file_path in enumerate(files_to_search, 1):
        if i % 1000 == 0:
            print(f"  Обработано файлов: {i}/{len(files_to_search)}")
            
        try:
            if file_path.name == 'Form.bin':
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
            else:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
            
            # Добавляем содержимое в общий индекс
            all_content += content + "\n"
            
        except Exception as e:
            print(f"Ошибка при чтении файла {file_path}: {e}")
            continue
    
    print("Поиск объектов в общем индексе...")
    
    # Теперь ищем каждый объект в общем индексе
    for i, object_name in enumerate(object_names, 1):
        if i % 5 == 0:
            print(f"Обработано объектов: {i}/{len(object_names)}")
            
        # Используем простой поиск строки вместо регулярных выражений для скорости
        count = all_content.lower().count(object_name.lower())
        
        # Ограничиваем результат до 100+ если слишком много
        if count > 100:
            count = 100
            print(f"  Объект {object_name}: 100+ вхождений (ограничено)")
        else:
            print(f"  Объект {object_name}: {count} вхождений")
        
        usage_counts[object_name] = count
    
    return usage_counts

def save_results_to_csv(usage_counts: Dict[str, int], object_name_to_path: Dict[str, Path], output_file: str):
    """
    Сохраняет результаты в CSV файл
    """
    with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        
        # Записываем заголовки
        writer.writerow(['Имя объекта', 'Путь к XML', 'Количество использований'])
        
        # Записываем данные
        for object_name, count in sorted(usage_counts.items(), key=lambda x: x[1], reverse=True):
            xml_path = str(object_name_to_path.get(object_name, ''))
            writer.writerow([object_name, xml_path, count])

def main():
    """
    Основная функция
    """
    # Путь к корню проекта (на два уровня выше папки Refactoring1C)
    project_root = Path(__file__).parent.parent
    
    print(f"Поиск объектов в проекте: {project_root}")
    
    # Получаем список имен объектов из XML файлов
    print("Извлечение имен объектов из XML файлов...")
    object_name_to_path = get_object_names_from_xml_files(project_root)
    object_names = list(object_name_to_path.keys())
    
    print(f"Найдено объектов: {len(object_names)}")
    
    # Обрабатываем все объекты
    print(f"Будем обрабатывать все {len(object_names)} объектов")
    
    # Подсчитываем использование каждого объекта
    print("Подсчет использования объектов...")
    usage_counts = count_object_usage(project_root, object_names)
    
    # Сохраняем результаты в CSV файл
    output_file = Path(__file__).parent / "object_usage_statistics.csv"
    save_results_to_csv(usage_counts, object_name_to_path, output_file)
    
    print(f"Результаты сохранены в файл: {output_file}")
    
    # Выводим статистику
    total_objects = len(usage_counts)
    objects_with_usage = sum(1 for count in usage_counts.values() if count > 0)
    max_usage = max(usage_counts.values()) if usage_counts else 0
    
    print(f"\nСтатистика:")
    print(f"Всего объектов: {total_objects}")
    print(f"Объектов с использованием: {objects_with_usage}")
    print(f"Максимальное количество использований: {max_usage}")

if __name__ == "__main__":
    main()
