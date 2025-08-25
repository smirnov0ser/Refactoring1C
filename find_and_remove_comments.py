#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для поиска и удаления закомментированных блоков кода в проекте 1С
Правила удаления:
1. НЕ удаляет комментарии методов (блоки перед Процедура/Функция)
2. Ищет блоки из более чем 9 строк закомментированного кода (не включая пустые строки между ними)
3. Расширяет блок кода вверх и вниз, добавляя пустые строки и строки комментариев, пока не встретит код или описание метода. 
Не добавляет в блок первую пустую строку полученного блока. если такой нет - последнюю пустую строку. 
"""

import os
import re
import glob
import sys
from pathlib import Path

# Константы
MIN_COMMENT_BLOCK_LINES = 20 # Минимальное количество содержательных закомментированных строк в блоке для удаления

# Regex для определения строк комментариев
COMMENT_REGEX = re.compile(r'^\s*//')
# Regex для определения пустых строк (включая строки только с пробелами)
EMPTY_LINE_REGEX = re.compile(r'^\s*$')
# Regex для определения объявлений процедур и функций
METHOD_DECLARATION_REGEX = re.compile(r'^\s*(&\w+\s*)?(Процедура|Функция)\s+\w+')

def is_comment(line):
    """Проверяет, является ли строка комментарием 1С."""
    return bool(COMMENT_REGEX.match(line))

def is_empty_line(line):
    """Проверяет, является ли строка пустой (или содержит только пробелы)."""
    return bool(EMPTY_LINE_REGEX.match(line))

def is_method_declaration(line):
    """Проверяет, является ли строка объявлением Процедуры или Функции."""
    return bool(METHOD_DECLARATION_REGEX.match(line))

def count_commented_lines_in_block(lines, start_index, end_index):
    """
    Считает количество закомментированных строк в заданном блоке,
    исключая пустые строки.
    """
    count = 0
    for i in range(start_index, end_index + 1):
        if is_comment(lines[i]) and not is_empty_line(lines[i]):
            count += 1
    return count

def expand_comment_block(lines, start_index, end_index):
    """
    Расширяет блок закомментированного кода вверх и вниз,
    добавляя пустые строки и строки комментариев, пока не встретит код или описание метода.
    Не добавляет в блок первую пустую строку полученного блока, если такой нет - последнюю пустую строку.
    """
    expanded_start = start_index
    expanded_end = end_index

    # Расширяем вверх
    temp_start = start_index - 1
    first_empty_line_found_up = -1
    while temp_start >= 0:
        line = lines[temp_start]
        if is_method_declaration(line) or (not is_comment(line) and not is_empty_line(line)):
            break
        if is_empty_line(line):
            if first_empty_line_found_up == -1:
                first_empty_line_found_up = temp_start
            expanded_start = temp_start
        elif is_comment(line):
            expanded_start = temp_start
        temp_start -= 1

    # Если первая пустая строка была найдена и она не является первой строкой блока, исключаем её
    if first_empty_line_found_up != -1 and first_empty_line_found_up == expanded_start and not is_comment(lines[first_empty_line_found_up + 1]):
        expanded_start += 1

    # Расширяем вниз
    temp_end = end_index + 1
    last_empty_line_found_down = -1
    while temp_end < len(lines):
        line = lines[temp_end]
        if is_method_declaration(line) or (not is_comment(line) and not is_empty_line(line)):
            break
        if is_empty_line(line):
            if last_empty_line_found_down == -1:
                last_empty_line_found_down = temp_end
            expanded_end = temp_end
        elif is_comment(line):
            expanded_end = temp_end
        temp_end += 1

    # Если последняя пустая строка была найдена и она не является последней строкой блока, исключаем её
    if last_empty_line_found_down != -1 and last_empty_line_found_down == expanded_end and not is_comment(lines[last_empty_line_found_down - 1]):
        expanded_end -= 1

    return expanded_start, expanded_end

def remove_commented_blocks(file_path):
    #print(f"Processing file: {file_path}")
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()

    new_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if is_comment(line):
            # Поиск конца блока комментариев
            block_start = i
            block_end = i
            while block_end + 1 < len(lines) and (is_comment(lines[block_end + 1]) or is_empty_line(lines[block_end + 1])):
                block_end += 1

            # Проверяем, является ли это комментарием метода
            is_method_comment = False
            # Ищем описание метода после блока комментариев (непосредственно после него или через пустые строки)
            j = block_end + 1
            while j < len(lines) and is_empty_line(lines[j]):
                j += 1
            if j < len(lines) and is_method_declaration(lines[j]):
                is_method_comment = True

            if not is_method_comment:
                # Считаем количество содержательных закомментированных строк
                num_commented_lines = count_commented_lines_in_block(lines, block_start, block_end)

                if num_commented_lines > MIN_COMMENT_BLOCK_LINES:
                    # Расширяем блок для удаления
                    expanded_start, expanded_end = expand_comment_block(lines, block_start, block_end)
                    print(f"  Found block to remove from line {expanded_start + 1} to {expanded_end + 1} with {num_commented_lines} commented lines")
                    i = expanded_end + 1  # Пропускаем удаленный блок
                    continue

        new_lines.append(line)
        i += 1

    # Записываем изменения только если они есть
    if new_lines != lines:
        print(f"  Changes detected, writing to file: {file_path}")
        with open(file_path, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)
    #else:
        #print(f"  No changes detected for file: {file_path}")

if __name__ == "__main__":
    target_path = Path.cwd() # Текущая директория
    print(f"Searching for 1C files in: {target_path}")
    for file_path in glob.glob(str(target_path / "**/*.bin"), recursive=True):
        remove_commented_blocks(file_path)
    for file_path in glob.glob(str(target_path / "**/*.bsl"), recursive=True):
        remove_commented_blocks(file_path)
    for file_path in glob.glob(str(target_path / "**/*.prc"), recursive=True):
        remove_commented_blocks(file_path)
    for file_path in glob.glob(str(target_path / "**/*.os"), recursive=True):
        remove_commented_blocks(file_path)
    
