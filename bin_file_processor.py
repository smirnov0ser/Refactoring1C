import re
from pathlib import Path
from typing import Optional, Tuple
import subprocess
import shutil
import tempfile
import os

# -----------------------------
# Universal helpers for 1C .bin
# -----------------------------

def resolve_v8unpack_exe() -> Tuple[Optional[str], Optional[str]]:
    """Try to resolve path to v8unpack_local.exe via PATH, script dir, and CWD."""
    exe_name = "v8unpack_local.exe"
    # 1) PATH
    from shutil import which
    found = which(exe_name)
    if found:
        return found, None
    # 2) Script directory
    script_dir = Path(__file__).resolve().parent
    candidate = script_dir / exe_name
    if candidate.exists():
        return str(candidate), None
    # 3) Current working directory
    cwd_candidate = Path.cwd() / exe_name
    if cwd_candidate.exists():
        return str(cwd_candidate), None
    return None, (
        "Не найден v8unpack_local.exe. Добавьте его в PATH, либо положите рядом с скриптами в Refactoring1C, "
        "или в текущий рабочий каталог."
    )


def unpack_bin_to_temp(file_path: str) -> Tuple[Optional[Path], Optional[str]]:
    """Unpack a .bin file to a unique temporary directory using v8unpack_local.exe."""
    original_file_path = Path(file_path)
    if not original_file_path.exists():
        return None, f"Файл не найден: {file_path}"
    try:
        exe_path, err = resolve_v8unpack_exe()
        if err:
            return None, err
        temp_dir = Path(tempfile.mkdtemp(prefix="v8unpack_temp_"))
        unpack_command = [exe_path, "-unpack", str(original_file_path), str(temp_dir)]
        result = subprocess.run(
            unpack_command,
            capture_output=True,
            text=True,
            check=False,
            encoding='cp866',
            errors='replace'
        )
        if result.returncode != 0:
            shutil.rmtree(temp_dir, ignore_errors=True)
            return None, f"Ошибка при распаковке файла {original_file_path}: {result.stderr or result.stdout}"
        return temp_dir, None
    except Exception as e:
        return None, f"Ошибка при распаковке файла {original_file_path}: {e}"


def find_module_file(unpacked_dir: Path) -> Tuple[Optional[Path], Optional[str]]:
    """Locate module.data inside the unpacked directory tree."""
    try:
        candidate = unpacked_dir / "src" / "module.data"
        if candidate.exists():
            return candidate, None
        found = list(unpacked_dir.glob("**/module.data"))
        if len(found) == 1:
            return found[0], None
        if len(found) == 0:
            return None, f"Не удалось найти module.data в {unpacked_dir} после распаковки."
        return None, f"Найдено несколько module.data в {unpacked_dir}. Уточните выбор."
    except Exception as e:
        return None, f"Ошибка поиска module.data в {unpacked_dir}: {e}"


def read_module_text(unpacked_dir: Path, encoding: str = 'utf-8') -> Tuple[Optional[str], Optional[str]]:
    """Read and return text of module.data from unpacked directory."""
    module_path, err = find_module_file(unpacked_dir)
    if err:
        return None, err
    try:
        return module_path.read_text(encoding=encoding, errors='ignore'), None
    except Exception as e:
        return None, f"Ошибка чтения {module_path}: {e}"


def write_module_text(unpacked_dir: Path, content: str, encoding: str = 'utf-8') -> Optional[str]:
    """Write provided text to module.data inside unpacked directory."""
    module_path, err = find_module_file(unpacked_dir)
    if err:
        return err
    try:
        module_path.write_text(content, encoding=encoding)
        return None
    except Exception as e:
        return f"Ошибка записи {module_path}: {e}"


def pack_temp_to_bin(unpacked_dir: Path, out_bin_path: Path) -> Optional[str]:
    """Pack unpacked directory back to .bin using v8unpack_local.exe."""
    try:
        exe_path, err = resolve_v8unpack_exe()
        if err:
            return err
        pack_command = [exe_path, "-pack", str(unpacked_dir), str(out_bin_path)]
        result = subprocess.run(
            pack_command,
            capture_output=True,
            text=True,
            check=False,
            encoding='cp866',
            errors='replace'
        )
        if result.returncode != 0:
            return f"Ошибка при упаковке файла из {unpacked_dir}: {result.stderr or result.stdout}"
        return None
    except Exception as e:
        return f"Ошибка при упаковке файла из {unpacked_dir}: {e}"


# ---------------------------------
# High-level processor (kept stable)
# ---------------------------------

def process_bin_file(file_path: str, modification_func) -> Tuple[bool, Optional[str]]:
    """
    Unpacks a .bin file, reads module text, applies modification_func(content)->(new_content, was_modified),
    repacks into a new .bin, replaces the original on success, and cleans up temporaries.
    """
    original_file_path = Path(file_path)
    if not original_file_path.exists():
        return False, f"Файл не найден: {file_path}"

    temp_dir: Optional[Path] = None
    temp_new_bin_path: Optional[Path] = None
    try:
        # Unpack
        temp_dir, err = unpack_bin_to_temp(file_path)
        if err:
            return False, err

        # Read module text
        module_text, err = read_module_text(temp_dir)
        if err:
            return False, err

        # Modify
        modified_text, was_modified = modification_func(module_text)
        if not was_modified:
            return False, None

        # Write module text
        err = write_module_text(temp_dir, modified_text)
        if err:
            return False, err

        # Pack
        temp_new_bin_path = original_file_path.parent / (original_file_path.stem + ".new.bin")
        err = pack_temp_to_bin(temp_dir, temp_new_bin_path)
        if err:
            return False, err

        # Replace original
        shutil.copy(str(temp_new_bin_path), str(original_file_path))
        #print(f"+ {original_file_path}     Успешно обработан и обновлен.")
        return True, None

    except Exception as e:
        return False, f"Ошибка при обработке файла {original_file_path}: {e}"
    finally:
        # Cleanup
        if temp_dir and temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)
        if temp_new_bin_path and temp_new_bin_path.exists():
            try:
                os.remove(temp_new_bin_path)
            except Exception:
                pass
