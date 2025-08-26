#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для поиска и удаления блоков пустых строк и закомментированных блоков в проекте 1С
Правила удаления:
1. Ищет блоки из более чем X последовательных пустых строк.
2. Расширяет блок кода вверх и вниз, добавляя пустые строки и строки комментариев, пока не встретит код.
3. Не добавляет в блок первую пустую строку полученного блока, если такой нет - последнюю пустую строку.
4. НЕ удаляет комментарии методов (блоки перед Процедура/Функция).
"""

import os
import re
import glob
import sys
from pathlib import Path
from bin_file_processor import process_bin_file
from typing import Tuple

# Константы
MIN_EMPTY_LINES_BLOCK = 10 # Минимальное количество последовательных пустых строк в блоке для удаления

# Regex для определения строк комментариев
COMMENT_REGEX = re.compile(r'^\s*//')
# Regex для определения пустых строк (включая строки только с пробелами)
EMPTY_LINE_REGEX = re.compile(r'^\s*$')
# Regex для определения объявлений процедур и функций
METHOD_DECLARATION_REGEX = re.compile(r'^\s*(&\w+\s*)?(Процедура|Функция)\s+\w+')

def is_empty_line(line):
    """Проверяет, является ли строка пустой (или содержит только пробелы)."""
    return bool(EMPTY_LINE_REGEX.match(line))

def is_comment(line):
    """Проверяет, является ли строка комментарием 1С."""
    return bool(COMMENT_REGEX.match(line))

def is_method_declaration(line):
    """Проверяет, является ли строка объявлением Процедуры или Функции."""
    return bool(METHOD_DECLARATION_REGEX.match(line))

def count_empty_lines_in_block(lines, start_index, end_index):
    """Считает количество последовательных пустых строк в заданном блоке."""
    count = 0
    for i in range(start_index, end_index + 1):
        if is_empty_line(lines[i]):
            count += 1
    return count

def expand_empty_block(lines, start_index, end_index):
    """
    Расширяет блок пустых строк вверх и вниз,
    добавляя пустые строки и строки комментариев, пока не встретит код.
    Не добавляет в блок первую пустую строку полученного блока, если такой нет - последнюю пустую строку.
    """
    expanded_start = start_index
    expanded_end = end_index

    # Расширяем вверх
    temp_start = start_index - 1
    while temp_start >= 0:
        line = lines[temp_start]
        if is_method_declaration(line) or (not is_empty_line(line) and not is_comment(line)):
            break  # Останавливаемся на коде или объявлении метода
        expanded_start = temp_start
        temp_start -= 1

    # Расширяем вниз
    temp_end = end_index + 1
    while temp_end < len(lines):
        line = lines[temp_end]
        if is_method_declaration(line) or (not is_empty_line(line) and not is_comment(line)):
            break  # Останавливаемся на коде или объявлении метода
        expanded_end = temp_end
        temp_end += 1

    # Применяем правило обрезки: "Не добавляет в блок первую пустую строку полученного блока. если такой нет - последнюю пустую строку."
    # Это означает: если первая строка расширенного блока является пустой, и за ней следует НЕ пустая строка и НЕ комментарий (т.е. код),
    # то исключаем эту первую пустую строку. Аналогично для последней пустой строки.

    # Обрезаем ведущую пустую строку, если за ней следует "код"
    if expanded_start <= expanded_end and \
       is_empty_line(lines[expanded_start]) and \
       (expanded_start + 1 <= expanded_end) and \
       not is_empty_line(lines[expanded_start + 1]) and \
       not is_comment(lines[expanded_start + 1]) and \
       not is_method_declaration(lines[expanded_start + 1]):
        expanded_start += 1

    # Обрезаем конечную пустую строку, если ей предшествует "код"
    if expanded_start <= expanded_end and \
       is_empty_line(lines[expanded_end]) and \
       (expanded_end - 1 >= expanded_start) and \
       not is_empty_line(lines[expanded_end - 1]) and \
       not is_comment(lines[expanded_end - 1]) and \
       not is_method_declaration(lines[expanded_end - 1]):
        expanded_end -= 1

    return expanded_start, expanded_end

def remove_empty_blocks(file_path: str) -> bool:
    def _remove_empty_blocks_from_content(content: str) -> Tuple[str, bool]:
        lines = content.splitlines(keepends=True)

        new_lines = []
        i = 0
        changed = False
        while i < len(lines):
            line = lines[i]
            if is_empty_line(line):
                block_start = i
                block_end = i
                while block_end + 1 < len(lines) and (is_empty_line(lines[block_end + 1]) or is_comment(lines[block_end + 1])):
                    block_end += 1

                is_method_comment_block = False
                j = block_end + 1
                while j < len(lines) and (is_empty_line(lines[j]) or is_comment(lines[j])):
                    j += 1
                if j < len(lines) and is_method_declaration(lines[j]):
                    is_method_comment_block = True

                if not is_method_comment_block:
                    num_empty_lines = count_empty_lines_in_block(lines, block_start, block_end)

                    if num_empty_lines >= MIN_EMPTY_LINES_BLOCK:
                        expanded_start, expanded_end = expand_empty_block(lines, block_start, block_end)
                        print(f"  Found empty/comment block to remove from line {expanded_start + 1} to {expanded_end + 1} with {num_empty_lines} empty lines")
                        i = expanded_end + 1  # Пропускаем удаленный блок
                        changed = True
                        continue

            new_lines.append(line)
            i += 1

        return "".join(new_lines), changed

    if file_path.lower().endswith('.bin'):
        # Only process form binaries
        if os.path.basename(file_path).lower() != 'form.bin':
            return False
        was_modified, error_message = process_bin_file(file_path, _remove_empty_blocks_from_content)
        if error_message:
            print(f"!! {file_path}     {error_message}")
        return was_modified
    else:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        modified_content, changed = _remove_empty_blocks_from_content(content)

        if changed:
            print(f"  Changes detected, writing to file: {file_path}")
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(modified_content)
        return changed

if __name__ == "__main__":
    target_path = Path.cwd() # Текущая директория
    print(f"Searching for files in: {target_path}")
    for file_path in glob.glob(str(target_path / "**/*.bsl"), recursive=True):
        remove_empty_blocks(file_path)
    for file_path in glob.glob(str(target_path / "**/*.prc"), recursive=True):
        remove_empty_blocks(file_path)
    for file_path in glob.glob(str(target_path / "**/*.os"), recursive=True):
        remove_empty_blocks(file_path)
    for file_path in glob.glob(str(target_path / "**/*.bin"), recursive=True):
        remove_empty_blocks(file_path)
