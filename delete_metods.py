#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для поиска файлов и удаления методов из МетодыКУдалению.txt
"""

import re
import os
from pathlib import Path
from find_code_file import CodeFileFinder


def parse_methods_file(file_path: str) -> list:
    """
    Парсит файл МетодыКУдалению.txt
    
    Args:
        file_path: Путь к файлу
        
    Returns:
        Список кортежей (путь_к_объекту, описание_метода)
    """
    methods = []
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if line:
                    # Разделяем по первому пробелу
                    parts = line.split(' ', 1)
                    if len(parts) == 2:
                        object_path = parts[0]
                        method_description = parts[1]
                        methods.append((object_path, method_description, line_num))
                    else:
                        print(f"Предупреждение: строка {line_num} не содержит описание метода: {line}")
    except Exception as e:
        print(f"Ошибка при чтении файла: {e}")
    
    return methods


def extract_method_name(method_description: str) -> str:
    """
    Извлекает имя метода из описания
    
    Args:
        method_description: Описание метода
        
    Returns:
        Имя метода
    """
    # Ищем имя метода в кавычках
    match = re.search(r'"([^"]+)"', method_description)
    if match:
        return match.group(1)
    
    # Если кавычек нет, ищем после двоеточия
    match = re.search(r':\s*"([^"]+)"', method_description)
    if match:
        return match.group(1)
    
    # Если и это не сработало, берем последнее слово
    words = method_description.split()
    if words:
        return words[-1].strip('"')
    
    return ""


def remove_method_from_file(file_path: str, method_name: str) -> bool:
    """
    Удаляет метод из файла
    
    Args:
        file_path: Путь к файлу
        method_name: Имя метода для удаления
        
    Returns:
        True если метод был удален, False если не найден
    """
    try:
        # Читаем файл с игнорированием ошибок кодировки для .bin файлов
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        # Простой и быстрый паттерн для поиска методов
        pattern = rf'(?:Процедура|Функция)\s+{re.escape(method_name)}\s*\([^)]*\).*?(?:КонецПроцедуры|КонецФункции)'
        
        match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
        method_found = False
        
        if match:
            # Извлекаем первую строку объявления метода для проверки экспорта
            method_text = match.group(0)
            first_line = method_text.split('\n')[0]
            
            # Проверяем, есть ли слово "Экспорт" в первой строке
            if 'Экспорт' in first_line:
                print(f"!! {file_path}     Метод '{method_name}' НЕ удален - является экспортным")
            else:
                all_lines = content.splitlines(keepends=True)
                
                # Find the line index of the method's start
                char_count = 0
                method_start_line_idx = -1
                for idx, line_text in enumerate(all_lines):
                    if char_count == match.start(): # Exact start of line
                        method_start_line_idx = idx
                        break
                    if char_count < match.start() < char_count + len(line_text): # Match starts within a line
                        method_start_line_idx = idx
                        break
                    char_count += len(line_text)
                
                if method_start_line_idx == -1: # Should not happen if match is found
                    print(f"Error: Could not find start line for method {method_name}")
                    return False

                # Count comment lines directly above
                num_comment_lines_to_remove = 0
                for i in reversed(range(method_start_line_idx)):
                    line = all_lines[i].strip()
                    if line.startswith('//') or line.startswith('&'):
                        num_comment_lines_to_remove += 1
                    elif line == '': # Empty line, stop deleting comments
                        break
                    else: # Non-comment, non-empty line, stop deleting comments
                        break
                
                # Calculate the effective start line index for deletion
                effective_start_line_idx = method_start_line_idx - num_comment_lines_to_remove
                
                # The end of the block to remove is the end of the method match.
                # Find the line index of the method's end (match.end())
                char_count = 0
                method_end_line_idx = -1
                for idx, line_text in enumerate(all_lines):
                    char_count += len(line_text)
                    if char_count >= match.end(): # Match ends within or at the end of this line
                        method_end_line_idx = idx
                        break
                
                if method_end_line_idx == -1: # Should not happen if match is found
                    print(f"Error: Could not find end line for method {method_name}")
                    return False
                
                # Reconstruct content, excluding the identified lines
                # This removes lines from effective_start_line_idx to method_end_line_idx (inclusive)
                content = "".join(all_lines[:effective_start_line_idx] + all_lines[method_end_line_idx + 1:])
                
                method_found = True
                #print(f"+ {file_path}    Удален метод: {method_name}")
        
        if method_found:
            # Записываем измененный файл
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        else:
            print(f"!! {file_path}     Метод не найден: {method_name}")
            return False
            
    except Exception as e:
        print(f"!!  {file_path}    Ошибка при обработке файла: {e}")
        return False


def main():
    """Основная функция"""
    # Создаем экземпляр поисковика
    finder = CodeFileFinder()
    
    # Парсим файл с методами
    file_path = "МетодыКУдалению.txt"
    if not Path(file_path).exists():
        print(f"Файл {file_path} не найден!")
        return
    
    print(f"Читаю файл: {file_path}")
    methods = parse_methods_file(file_path)
    
    print(f"Найдено {len(methods)} записей для обработки")
    print("=" * 80)
    
    # Обрабатываем каждую запись
    processed_files = set()  # Множество уже обработанных файлов
    total_methods_removed = 0
    
    for i, (object_path, method_description, line_num) in enumerate(methods, 1):
        #print(f"[{i}/{len(methods)}] Обрабатываю: {object_path}")
        #print(f"  Описание: {method_description}")
        
        # Ищем файл
        result = finder.find_code_file(object_path)
        
        if result:
            file_path = result[0]  # Берем первый найденный файл
            #print(f"  Файл: {file_path}")
            
            # Извлекаем имя метода
            method_name = extract_method_name(method_description)
            if method_name:
                #print(f"  Метод для удаления: {method_name}")
                
                # Удаляем метод из файла
                if remove_method_from_file(file_path, method_name):
                    total_methods_removed += 1
                
                processed_files.add(file_path)
            else:
                print(f"!! {object_path}  Не удалось извлечь имя метода из: {method_description}")
        else:
            print(f"!! {object_path}  ❌ Файл не найден")
    
    # Итоговая статистика
    print("=" * 80)
    print(f"ИТОГО:")
    print(f"  Обработано записей: {len(methods)}")
    print(f"  Обработано файлов: {len(processed_files)}")
    print(f"  Удалено методов: {total_methods_removed}")
    


if __name__ == "__main__":
    main()
