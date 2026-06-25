#!/usr/bin/env python3
"""forgotpass — восстановление забытых паролей к защищённым файлам.

Использование:
    python3 recover.py <файл> [опции]

Примеры:
    python3 recover.py document.xlsx
    python3 recover.py secret.pdf --wordlist /path/to/dict.txt
    python3 recover.py archive.7z --mask "?d?d?d?d?d?d"
    python3 recover.py file.xlsx --password 123459 --decrypt-only
    python3 recover.py --list-formats

Алгоритм:
    1. Автоопределение формата (Office/PDF/7z/RAR/ZIP)
    2. Извлечение хэша (встроенный экстрактор или *2john)
    3. Перебор паролей через hashcat (словарь + rules или маска)
    4. Расшифровка файла найденным паролем
"""
from __future__ import annotations

import argparse
import os
import sys

# Добавляем каталог проекта в path для импорта lib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lib.detect import detect, list_supported, FormatInfo
from lib.extract import extract_hash
from lib.crack import crack_wordlist, crack_mask
from lib.decrypt import decrypt


BANNER = r"""
  _____ ___ _   _ _____ ____ ___ _____   __
 |  ___|_ _| \ | | ____/ ___|_ _|_   _| / /
 | |_   | ||  \| |  _|| |    | |  | |  / /
 |  _|  | || |\  | |__| |___ | |  | | / /
 |_|   |___|_| \_|_____\____|___| |_| /_/
        Восстановление забытых паролей v1.0.0
"""


def print_info(msg: str):
    print(f"[*] {msg}")


def print_ok(msg: str):
    print(f"[+] {msg}")


def print_err(msg: str):
    print(f"[!] {msg}", file=sys.stderr)


def print_warn(msg: str):
    print(f"[!] {msg}")


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="recover.py",
        description="Восстановление забытых паролей к защищённым файлам (Office, PDF, архивы).",
        epilog="Поддерживаемые форматы: MS Office 2007-2016, PDF, 7-Zip, RAR, ZIP.",
    )
    parser.add_argument("file", nargs="?", help="путь к защищённому файлу")
    parser.add_argument("--wordlist", "-w", metavar="PATH",
                        help="словарь для атаки (по умолчанию rockyou.txt + best64.rule)")
    parser.add_argument("--rule", default="best64.rule",
                        help="rules-файл hashcat (по умолчанию best64.rule, 'none' — без rules)")
    parser.add_argument("--mask", "-m", metavar="MASK",
                        help="брутфорс по маске hashcat (напр. '?d?d?d?d?d?d')")
    parser.add_argument("--increment-min", type=int, default=1,
                        help="мин. длина для --mask --increment (по умолч. 1)")
    parser.add_argument("--increment-max", type=int, default=8,
                        help="макс. длина для --mask --increment (по умолч. 8)")
    parser.add_argument("--no-increment", action="store_true",
                        help="отключить --increment для маски (только указанная длина)")
    parser.add_argument("--password", "-p",
                        help="расшифровать с известным паролем (без перебора)")
    parser.add_argument("--decrypt-only", action="store_true",
                        help="только расшифровать (требует --password)")
    parser.add_argument("--output", "-o",
                        help="путь для расшифрованного файла (по умолч. <имя>_decrypted.<ext>)")
    parser.add_argument("--hash-only", action="store_true",
                        help="только извлечь и вывести хэш, без перебора")
    parser.add_argument("--list-formats", action="store_true",
                        help="показать поддерживаемые форматы и выйти")
    parser.add_argument("--no-decrypt", action="store_true",
                        help="найти пароль, но не расшифровывать файл")

    args = parser.parse_args()

    if args.list_formats:
        list_supported()
        return 0

    if not args.file:
        parser.print_help()
        return 1

    if not os.path.isfile(args.file):
        print_err(f"Файл не найден: {args.file}")
        return 1

    print(BANNER)

    # --- Режим: только расшифровка с известным паролем ---
    if args.decrypt_only:
        if not args.password:
            print_err("--decrypt-only требует --password")
            return 1
        return do_decrypt_only(args)

    # --- Шаг 1: определение формата ---
    print_info(f"Анализ файла: {args.file}")
    info = detect(args.file)
    if not info:
        print_err("Формат не распознан или файл не зашифрован.")
        print_err("Поддерживаемые форматы: MS Office, PDF, 7-Zip, RAR, ZIP.")
        print_err("Запустите с --list-formats для подробного списка.")
        return 2

    print_ok(f"Формат: {info.name} ({info.description})")
    print_ok(f"Режим hashcat: {info.hashcat_mode}")

    # --- Шаг 2: извлечение хэша ---
    print_info("Извлечение хэша...")
    hash_str = extract_hash(args.file, info)
    if not hash_str:
        print_err("Не удалось извлечь хэш.")
        return 3
    print_ok(f"Хэш: {hash_str[:80]}{'...' if len(hash_str) > 80 else ''}")

    if args.hash_only:
        print(hash_str)
        return 0

    # --- Режим: расшифровка с указанным паролем (с проверкой) ---
    if args.password:
        print_info(f"Проверка указанного пароля: {args.password!r}")
        # Для проверки можно запустить расшифровку напрямую
        out = args.output or default_output(args.file, info)
        if decrypt(args.file, args.password, out, info.decryptor):
            print_ok(f"Пароль верный! Файл расшифрован: {out}")
            return 0
        else:
            print_err("Указанный пароль неверен.")
            return 4

    # --- Шаг 3: перебор паролей ---
    print_info("Запуск перебора паролей через hashcat...")
    password = None
    if args.mask:
        print_info(f"Режим: брутфорс по маске {args.mask!r}")
        password = crack_mask(
            hash_str, info.hashcat_mode,
            mask=args.mask,
            increment=not args.no_increment,
            increment_min=args.increment_min,
            increment_max=args.increment_max,
        )
    else:
        rule = None if args.rule.lower() == "none" else args.rule
        if rule:
            print_info(f"Режим: словарь + rules ({rule})")
        else:
            print_info("Режим: словарь (без rules)")
        password = crack_wordlist(
            hash_str, info.hashcat_mode,
            wordlist=args.wordlist,
            rule=rule,
        )

    if not password:
        print_err("Пароль не найден.")
        print_err("Попробуйте:")
        print_err("  - другой словарь (--wordlist)")
        print_err("  - rules-файл (по умолчанию best64.rule, есть dive.rule, Incisive-leetspeak.rule)")
        print_err("  - брутфорс по маске (--mask '?d?d?d?d?d?d')")
        print_err("  - комбинированную атаку (словарь+словарь)")
        return 5

    print_ok(f"ПАРОЛЬ НАЙДЕН: {password!r}")

    # --- Шаг 4: расшифровка ---
    if args.no_decrypt:
        print_info("Расшифровка пропущена (--no-decrypt).")
        print(f"Пароль: {password}")
        return 0

    out = args.output or default_output(args.file, info)
    print_info(f"Расшифровка в {out} ...")
    if decrypt(args.file, password, out, info.decryptor):
        print_ok(f"Готово! Расшифрованный файл: {out}")
        print(f"\n  Пароль: {password}")
        print(f"  Файл:   {out}")
        return 0
    else:
        print_err("Расшифровка не удалась (пароль верный, но декодер ошибся).")
        print(f"  Пароль известен: {password}")
        print(f"  Попробуйте расшифровать вручную соответствующим инструментом.")
        return 6


def do_decrypt_only(args) -> int:
    """Расшифровка с известным паролем без определения формата."""
    info = detect(args.file)
    if not info:
        print_err("Формат не распознан.")
        return 2
    out = args.output or default_output(args.file, info)
    print_info(f"Формат: {info.name}")
    print_info(f"Расшифровка {args.file} -> {out} (пароль: {args.password!r})")
    if decrypt(args.file, args.password, out, info.decryptor):
        print_ok(f"Готово: {out}")
        return 0
    print_err("Расшифровка не удалась. Проверьте пароль.")
    return 6


def default_output(src: str, info: FormatInfo) -> str:
    """Сгенерировать имя выходного файла по умолчанию."""
    base, ext = os.path.splitext(src)
    if info.decryptor in ("sevenzip", "rar", "zip"):
        # Для архивов — каталог
        return base + "_extracted"
    return base + "_decrypted" + ext


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n[!] Прервано пользователем.", file=sys.stderr)
        sys.exit(130)
