#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для поиска и удаления закомментированных блоков кода в проекте 1С
Правила удаления:
1. НЕ удаляет комментарии методов (блоки перед Процедура/Функция)
2. Ищет блоки из более чем Х строк закомментированного кода (включая пустые строки между ними)
3. Расширяет блок кода вверх и вниз, добавляя пустые строки и строки комментариев, пока не встретит код или описание метода. 
Не добавляет в блок первую пустую строку полученного блока. если такой нет - последнюю пустую строку. 
"""

import os
import re
import glob
import sys
from pathlib import Path
from bin_file_processor import process_bin_file
from typing import Tuple

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
    """Проверяет, является ли строка объявлением Процедуры или Функции.
    Игнорирует строки-комментарии (//...).
    """
    l = line.lstrip()
    # Не считать комментарии объявлениями методов
    if l.startswith('//'):
        return False
    return bool(METHOD_DECLARATION_REGEX.match(l))

def count_commented_lines_in_block(lines, start_index, end_index):
    """
    Считает количество строк в заданном блоке, включая пустые строки между комментариями.
    """
    # В блок уже входят только строки, удовлетворяющие is_comment или is_empty_line,
    # поэтому считаем все строки блока целиком.
    return end_index - start_index + 1

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

def remove_commented_blocks(file_path: str) -> bool:
    def _remove_comments_from_content(content: str) -> Tuple[str, bool]:
        lines = content.splitlines(keepends=True)

        new_lines = []
        i = 0
        changed = False
        while i < len(lines):
            line = lines[i]
            if is_comment(line):
                block_start = i
                block_end = i
                while block_end + 1 < len(lines) and (is_comment(lines[block_end + 1]) or is_empty_line(lines[block_end + 1])):
                    block_end += 1

                # Проверяем, является ли это комментарием метода
                is_method_comment = False
                # Блок не может быть шапкой метода, если его последняя строка пустая
                if not is_empty_line(lines[block_end]):
                    j = block_end + 1
                    if j < len(lines):
                        lj = lines[j].lstrip()
                        if is_method_declaration(lines[j]):
                            is_method_comment = True
                        elif lj.startswith('&'):
                            # Допускаем один или несколько атрибутов перед объявлением метода
                            k = j
                            while k < len(lines) and lines[k].lstrip().startswith('&'):
                                k += 1
                            if k < len(lines) and is_method_declaration(lines[k]):
                                is_method_comment = True

                if not is_method_comment:
                    num_commented_lines = count_commented_lines_in_block(lines, block_start, block_end)

                    if num_commented_lines >= MIN_COMMENT_BLOCK_LINES:
                        expanded_start, expanded_end = expand_comment_block(lines, block_start, block_end)
                        print(f"  Found block to remove from line {expanded_start + 1} to {expanded_end + 1} with {num_commented_lines} commented lines")
                        # Skip the removed block
                        i = expanded_end + 1  
                        changed = True
                        continue

            new_lines.append(line)
            i += 1

        return "".join(new_lines), changed

    if file_path.lower().endswith('.bin'):
        # Only process form binaries
        if os.path.basename(file_path).lower() != 'form.bin':
            return False
        was_modified, error_message = process_bin_file(file_path, _remove_comments_from_content)
        if error_message:
            print(f"!! {file_path}     {error_message}")
        return was_modified
    else:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        modified_content, changed = _remove_comments_from_content(content)

        if changed:
            print(f"  Changes detected, writing to file: {file_path}")
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(modified_content)
        return changed

if __name__ == "__main__":
    target_path = Path.cwd() # Текущая директория
    print(f"Searching for 1C files in: {target_path}")
    for file_path in glob.glob(str(target_path / "**/*.bin"), recursive=True):
        remove_commented_blocks(file_path)
    for file_path in glob.glob(str(target_path / "**/*.bsl"), recursive=True):
        remove_commented_blocks(file_path)
    for file_path in glob.glob(str(target_path / "**/*.os"), recursive=True):
        remove_commented_blocks(file_path)
    
