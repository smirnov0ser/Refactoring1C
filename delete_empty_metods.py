#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для поиска файлов и удаления пустых методов из ПустыеМетодыКУдалению.txt
"""

import re
import os
from pathlib import Path
from find_code_file import CodeFileFinder


def parse_methods_file(file_path: str) -> list:
    """
    Парсит файл ПустыеМетодыКУдалению.txt
    
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
    Извлекает имя метода из описания, например, 'Пустой обработчик: "ПередЗагрузкойДанныхИзНастроекНаСервере"' -> 'ПередЗагрузкойДанныхИзНастроекНаСервере'
    
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
    Удаляет метод из файла, если он пустой (содержит только комментарии или пустые строки между началом и концом метода)
    
    Args:
        file_path: Путь к файлу
        method_name: Имя метода для удаления
        
    Returns:
        True если метод был удален, False если не найден или не пуст
    """
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        # Regex to find the method block, including optional 'Экспорт' keyword
        pattern = rf'(?:Процедура|Функция)\s+{re.escape(method_name)}\s*\([^)]*\).*?(?:КонецПроцедуры|КонецФункции)'
        
        # We need to search with DOTALL to match newlines within the method body
        match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
        method_found = False

        if match:
            # Extract the method text to check for emptiness
            method_text_full = match.group(0)
            
            # Extract the body for emptiness check (excluding the declaration and end lines)
            # This is a bit more involved as we need to find the actual body. A simpler regex might be better for this initial check.
            # For now, let's re-use the original body extraction but without named groups
            body_pattern = rf'(?:Процедура|Функция)\s+{re.escape(method_name)}\s*\([^)]*\)(?:Экспорт)?\s*(.*?)(?:КонецПроцедуры|КонецФункции)'
            body_match = re.search(body_pattern, method_text_full, re.DOTALL | re.IGNORECASE)
            method_body = body_match.group(1) if body_match else ""

            # Remove comments and empty lines from the method body
            cleaned_body = re.sub(r'(?m)^\s*(?://.*|&.*)?$\n?', '', method_body).strip()
            
            if not cleaned_body: # If the cleaned body is empty, the method is empty
                # Извлекаем первую строку объявления метода для проверки экспорта
                first_line = method_text_full.split('\n')[0]
                
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
                    # print(f"+ {file_path}    Удален пустой метод: {method_name}")
            else:
                print(f"!! {file_path}     Метод '{method_name}' НЕ удален - не является пустым")

        if method_found:
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
    finder = CodeFileFinder()
    
    file_path = Path(".") / "Refactoring1C" / "ПустыеМетодыКУдалению.txt"
    if not file_path.exists():
        print(f"Файл {file_path} не найден!")
        return
    
    print(f"Читаю файл: {file_path}")
    methods_to_delete = parse_methods_file(file_path)
    
    print(f"Найдено {len(methods_to_delete)} записей для обработки")
    print("=" * 80)
    
    processed_files = set()
    total_methods_removed = 0
    
    for i, (object_path, method_description, line_num) in enumerate(methods_to_delete, 1):
        #print(f"[{i}/{len(methods_to_delete)}] Обрабатываю: {object_path}")
        #print(f"  Описание: {method_description}")
        
        # Извлекаем имя метода
        method_name = extract_method_name(method_description)

        # Ищем файл
        result = finder.find_code_file(object_path)
        
        if result:
            file_path_found = result[0]  # Берем первый найденный файл
            #print(f"  Файл: {file_path_found}")
            
            if method_name:
                #print(f"  Метод для удаления: {method_name}")
                
                # Удаляем метод из файла
                if remove_method_from_file(file_path_found, method_name):
                    total_methods_removed += 1
                
                processed_files.add(file_path_found)
            else:
                print(f"!! {object_path}  Не удалось извлечь имя метода из: {method_description}")
        else:
            print(f"!! {object_path}  ❌ Файл не найден")
    
    print("=" * 80)
    print(f"ИТОГО:")
    print(f"  Обработано записей: {len(methods_to_delete)}")
    print(f"  Обработано файлов: {len(processed_files)}")
    print(f"  Удалено методов: {total_methods_removed}")

if __name__ == "__main__":
    main()
