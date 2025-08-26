import os
import re
import sys
from typing import List, Tuple
from bin_file_processor import process_bin_file


START_METHOD_TOKENS = ["Процедура", "Функция"]
END_METHOD_TOKENS = ["КонецПроцедуры", "КонецФункции"]

# Tokens to track nesting where Возврат должен быть проигнорирован
# Учет вложенности с учетом препроцессора: #Если/#ИначеЕсли/#КонецЕсли
NEST_INC_TOKENS = [
    "Если",
    "Попытка", 
    #"Цикл",
    "Для",
    "Пока",
    "#Если",
]
NEST_DEC_TOKENS = [
    "КонецЕсли",
    "КонецПопытки", 
    "КонецЦикла",
    "#КонецЕсли",
]

FILE_EXTENSIONS = {".os", ".bsl", ".bin"}

# Предкомпилированные паттерны (ускорение)
_START_RE = re.compile(r"^\s*(?:" + "|".join(map(re.escape, START_METHOD_TOKENS)) + r")\b")
_END_RE = re.compile(r"^\s*(?:" + "|".join(map(re.escape, END_METHOD_TOKENS)) + r")\b")
_RETURN_ONLY_RE = re.compile(r"^\s*Возврат\s*;\s*$")
_NEST_DEC_RE = re.compile(r"(^|\s)(?:" + "|".join(map(re.escape, NEST_DEC_TOKENS)) + r")(\s|$)")
_NEST_INC_RE = re.compile(r"(^|\s)(?:" + "|".join(map(re.escape, NEST_INC_TOKENS)) + r")(\s|$)")
_NEST_DEC_START_RE = re.compile(r"^\s*(?:" + "|".join(map(re.escape, NEST_DEC_TOKENS)) + r")\b", re.IGNORECASE)
_NEST_INC_START_RE = re.compile(r"^\s*(?:" + "|".join(map(re.escape, NEST_INC_TOKENS)) + r")\b", re.IGNORECASE)


def remove_string_literals(code: str) -> str:
    '''Удаляет строковые литералы 1С (двойные кавычки, с экранированием "") для упрощения поиска токенов.'''
    result = []
    i = 0
    in_str = False
    while i < len(code):
        ch = code[i]
        if not in_str:
            if ch == '"':
                in_str = True
                # заменяем содержимое строк на пробелы той же длины, чтобы не ломать позиции
                result.append(' ')
            else:
                result.append(ch)
            i += 1
        else:
            # внутри строки 1С, двойные кавычки удваиваются
            if ch == '"':
                if i + 1 < len(code) and code[i + 1] == '"':
                    # это экранированная кавычка внутри строки
                    result.append('  ')
                    i += 2
                else:
                    in_str = False
                    result.append(' ')
                    i += 1
            else:
                # гасим содержимое строки пробелами
                result.append(' ')
                i += 1
    return ''.join(result)


def strip_inline_comment(code: str) -> str:
    """Удаляет // комментарий вне строк."""
    s = remove_string_literals(code)
    idx = s.find("//")
    if idx >= 0:
        return code[:idx]
    return code


def is_preprocessor_line(line: str) -> bool:
    l = line.lstrip()
    return l.startswith('#')


def is_comment_line(line: str) -> bool:
    l = line.lstrip()
    return l.startswith('//')


def is_continuation_bar(line: str) -> bool:
    l = line.lstrip()
    return l.startswith('|')


def normalize(s: str) -> str:
    return remove_string_literals(strip_inline_comment(s))


def find_methods(lines: List[str]) -> List[Tuple[int, int]]:
    """Возвращает список границ методов как (start_idx, end_idx), включительно по end_idx."""
    methods = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if is_preprocessor_line(line):
            i += 1
            continue
        nl = normalize(line)
        # Старт метода должен быть в начале строки
        starts = _START_RE.search(nl) is not None
        if starts:
            start_idx = i
            j = i + 1
            while j < len(lines):
                if not is_preprocessor_line(lines[j]):
                    nl2 = normalize(lines[j])
                    # Конец метода тоже должен быть в начале строки
                    ends = _END_RE.search(nl2) is not None
                    if ends:
                        methods.append((start_idx, j))
                        i = j
                        break
                j += 1
            else:
                # Конца метода нет – считаем до конца файла
                methods.append((start_idx, len(lines) - 1))
                i = len(lines) - 1
        i += 1
    return methods


def should_ignore_return(line: str, nesting: int, lines: List[str] = None, current_idx: int = None, start_idx: int = None) -> bool:
    # Игнор по правилам пользователя
    if is_comment_line(line):
        return True
    if is_continuation_bar(line):
        return True
    if nesting > 0:
        return True

    # Проверяем, что это самостоятельный оператор Возврат;
    before_comment = strip_inline_comment(line)
    no_strings = remove_string_literals(before_comment)
    # Запрещаем случаи вроде Object.Возврат
    # Должно начинаться с Возврат и заканчиваться ; (с пробелами)
    pattern = r"^\s*Возврат\s*;\s*$"
    if not re.match(pattern, no_strings):
        return True
    
    # Дополнительная проверка: Возврат должен быть на корневом уровне метода
    # Проверяем, что от начала метода до текущей строки не было открытых условных блоков
    if lines is not None and current_idx is not None and start_idx is not None:
        temp_nesting = 0
        for k in range(start_idx + 1, current_idx + 1):
            temp_line = lines[k]
            temp_nl = normalize(temp_line)
            if _NEST_DEC_START_RE.search(temp_nl):
                temp_nesting = max(0, temp_nesting - 1)
            if _NEST_INC_START_RE.search(temp_nl):
                temp_nesting += 1
        
        # Если есть открытые условные блоки - игнорируем Возврат
        if temp_nesting > 0:
            return True
    
    # Также исключим случаи, где перед Возврат есть не пробел (напр. буква/точка)
    # Уже покрыто ^\s*
    return False


def process_method(lines: List[str], start_idx: int, end_idx: int) -> bool:
    """Обрабатывает метод. Возвращает True, если были изменения."""
    # Ищем первый безусловный Возврат;
    # Сканируем от первой строки тела до последней перед концом метода
    # Область удаления будет после строки с Возврат; до end_idx (не включая end токен)
    return_line_idx = None
    nesting = 0  # Инициализируем уровень вложенности

    # Сканируем только строки тела: после объявления и до строки конца метода
    for i in range(start_idx + 1, end_idx):
        line = lines[i]
        nl = normalize(line)

        if nl.strip() == "":
            continue

        # Сначала проверяем Возврат при текущем уровне вложенности
        if not should_ignore_return(line, nesting, lines, i, start_idx):
            return_line_idx = i
            break  # Нашли первый безусловный Возврат; - выходим из поиска

        # Затем накапливаем изменения вложенности по мере прохода
        if _NEST_DEC_START_RE.search(nl):
            nesting = max(0, nesting - 1)
        if _NEST_INC_START_RE.search(nl):
            nesting += 1

    if return_line_idx is None:
        return False

    # Определяем область удаления: с конца строки return до перед end_idx
    # По строкам это просто (return_line_idx+1 .. end_idx-1)
    delete_from = return_line_idx + 1
    delete_to = end_idx - 1
    if delete_from > delete_to:
        return False

    # Проверяем наличие хотя бы одной непустой строки
    has_non_empty = any(lines[k].strip() != "" for k in range(delete_from, delete_to + 1))
    if not has_non_empty:
        return False

    # Удаляем строки
    del lines[delete_from:delete_to + 1]
    return True


def process_file(path: str) -> Tuple[bool, int]:

    def _cleanup_returns_in_content(content: str) -> Tuple[str, bool]:
        # Нормализуем перевод строк к \n, сохраняя потом исходный стиль по первому вхождению
        newline = '\n'
        if '\r\n' in content:
            newline = '\r\n'
        lines = content.replace('\r\n', '\n').replace('\r', '\n').split('\n')

        methods = find_methods(lines)
        if not methods:
            return content, False

        changed = False
        changes_cnt = 0

        for start_idx, end_idx in reversed(methods):
            if end_idx >= len(lines):
                end_idx = len(lines) - 1
            if start_idx < 0 or end_idx <= start_idx:
                continue
            if process_method(lines, start_idx, end_idx):
                changed = True
                changes_cnt += 1
        
        return newline.join(lines), changed

    try:
        if path.lower().endswith('.bin'):
            # Only process form binaries
            if os.path.basename(path).lower() != 'form.bin':
                return False, 0
            was_modified, error_message = process_bin_file(path, _cleanup_returns_in_content)
            if error_message:
                print(f"!! {path}     {error_message}")
            return was_modified, (1 if was_modified else 0)
        else:
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            modified_content, changed = _cleanup_returns_in_content(content)

            if changed:
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(modified_content)
                return True, 1
            else:
                return False, 0
    except Exception as e:
        # print(f"!!  {path}    Ошибка при обработке файла: {e}") # Temporarily commented out to avoid excessive output
        return False, 0


def iter_source_files(root: str):
    if os.path.isfile(root):
        ext = os.path.splitext(root)[1].lower()
        if ext in FILE_EXTENSIONS:
            yield root
        return
    for dirpath, dirnames, filenames in os.walk(root):
        for name in filenames:
            ext = os.path.splitext(name)[1].lower()
            if ext in FILE_EXTENSIONS:
                yield os.path.join(dirpath, name)


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
    total_files = 0
    changed_files = 0
    total_methods_changed = 0
    for path in iter_source_files(root):
        total_files += 1
        changed, cnt = process_file(path)
        if changed:
            changed_files += 1
            total_methods_changed += cnt
            # print(f"Changed: {path} (methods cleaned: {cnt})")
    print(f"Processed files: {total_files}")
    print(f"Changed files: {changed_files}")
    print(f"Methods cleaned: {total_methods_changed}")


if __name__ == "__main__":
    main()


