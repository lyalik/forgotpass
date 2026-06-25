"""Запуск перебора паролей через hashcat.

Поддерживаемые режимы атаки:
    - wordlist:     словарь + опционально rules
    - mask:         брутфорс по маске (?l?l?l?d?d)
    - default:      словарь rockyou.txt + best64.rule (если есть)

hashcat работает с хэшем (быстро), не с полным файлом.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from typing import Optional


HASHCAT_BIN = shutil.which("hashcat") or "hashcat"

# Стандартные пути к rules-файлам hashcat
RULE_PATHS = [
    "/usr/share/hashcat/rules",
    os.path.expanduser("~/.local/share/hashcat/rules"),
]

# Стандартные пути к словарям
WORDLIST_PATHS = [
    "/usr/share/wordlists/rockyou.txt",
    os.path.expanduser("~/rockyou.txt"),
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "wordlists", "rockyou.txt"),
    "/usr/share/dict/words",
]


def find_rule(name: str = "best64.rule") -> Optional[str]:
    """Найти rules-файл hashcat."""
    for d in RULE_PATHS:
        p = os.path.join(d, name)
        if os.path.isfile(p):
            return p
    return None


def find_wordlist(preferred: Optional[str] = None) -> Optional[str]:
    """Найти словарь. Если preferred указан — проверить его, иначе искать стандартные."""
    if preferred:
        if os.path.isfile(preferred):
            return preferred
        print(f"[!] Указанный словарь не найден: {preferred}", file=sys.stderr)
    for p in WORDLIST_PATHS:
        if os.path.isfile(p) and os.path.getsize(p) > 0:
            return p
    return None


def _run_hashcat(args: list[str], potfile: Optional[str] = None) -> tuple[int, str]:
    """Запустить hashcat с заданными аргументами. Возвращает (exit_code, output)."""
    cmd = [HASHCAT_BIN, "--force", "-D", "1", "-w", "3", "--potfile-disable"]
    if potfile:
        cmd += ["-o", potfile]
    cmd += args
    print(f"[*] Запуск: {' '.join(cmd[:8])} ...", flush=True)
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=None)
        return result.returncode, result.stdout + result.stderr
    except KeyboardInterrupt:
        return 130, ""
    except Exception as e:
        return 1, str(e)


def crack_wordlist(
    hash_str: str,
    hashcat_mode: int,
    wordlist: Optional[str] = None,
    rule: Optional[str] = "best64.rule",
    outfile: Optional[str] = None,
) -> Optional[str]:
    """Атака по словарю (с rules). Возвращает найденный пароль или None."""
    wl = find_wordlist(wordlist)
    if not wl:
        print("[!] Словарь не найден. Укажите через --wordlist или установите rockyou.txt.", file=sys.stderr)
        print(f"    Стандартные пути: {WORDLIST_PATHS}", file=sys.stderr)
        return None

    with tempfile.NamedTemporaryFile(mode="w", suffix=".hash", delete=False) as hf:
        hf.write(hash_str + "\n")
        hash_file = hf.name

    potfile = outfile or tempfile.NamedTemporaryFile(suffix=".pot", delete=False).name

    args = ["-m", str(hashcat_mode), hash_file, wl]
    rule_path = None
    if rule:
        if os.path.isfile(rule):
            rule_path = rule
        else:
            rule_path = find_rule(rule)
        if rule_path:
            args += ["-r", rule_path]
        else:
            print(f"[!] Rules-файл {rule} не найден — перебор без мутаций.", file=sys.stderr)

    code, output = _run_hashcat(args, potfile=potfile)

    password = _read_potfile(potfile, hash_str)

    # Очистка временных файлов
    for f in (hash_file, potfile):
        try:
            if not outfile:
                os.unlink(f)
        except OSError:
            pass

    if "Cracked" in output or password:
        return password
    if code == 0 and not password:
        # hashcat завершился без находки
        return None
    return password


def crack_mask(
    hash_str: str,
    hashcat_mode: int,
    mask: str = "?d?d?d?d?d?d",
    increment: bool = True,
    increment_min: int = 1,
    increment_max: int = 8,
    outfile: Optional[str] = None,
) -> Optional[str]:
    """Брутфорс по маске (-a 3). Возвращает найденный пароль или None."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".hash", delete=False) as hf:
        hf.write(hash_str + "\n")
        hash_file = hf.name

    potfile = outfile or tempfile.NamedTemporaryFile(suffix=".pot", delete=False).name

    args = ["-m", str(hashcat_mode), "-a", "3", hash_file, mask]
    if increment:
        args += ["--increment"]
        args += ["--increment-min", str(increment_min)]
        args += ["--increment-max", str(increment_max)]

    code, output = _run_hashcat(args, potfile=potfile)
    password = _read_potfile(potfile, hash_str)

    for f in (hash_file, potfile):
        try:
            if not outfile:
                os.unlink(f)
        except OSError:
            pass

    return password


def _read_potfile(potfile: str, hash_str: str) -> Optional[str]:
    """Прочитать potfile и извлечь пароль для данного хэша."""
    if not potfile or not os.path.isfile(potfile):
        return None
    try:
        with open(potfile, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                # Формат: hash:password
                if ":" in line:
                    h, _, pw = line.partition(":")
                    # hash может содержать двоеточия (например $office$*...),
                    # поэтому сравниваем по началу
                    if h.startswith("$") and hash_str.split(":")[0].split("*")[0] in h:
                        return pw
                    if h == hash_str:
                        return pw
                    # fallback: последний сегмент после последнего двоеточия
                    if line.startswith(hash_str):
                        return line[len(hash_str) + 1:]
    except Exception:
        pass
    return None
