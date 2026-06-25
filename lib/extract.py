"""Извлечение хэша из защищённого файла.

Используются *2john утилиты из John the Ripper Jumbo (устанавливаются через
install.sh). Для MS Office также есть встроенный Python-экстрактор как fallback.

Возвращает строку хэша в формате, понятном hashcat ($office$*, $pdf$*, и т.д.).
John и hashcat используют совместимый формат для большинства типов.
"""
from __future__ import annotations

import base64
import os
import shutil
import struct
import subprocess
import sys
import tempfile
from typing import Optional

from .detect import FormatInfo


# Пути поиска *2john утилит (install.sh кладёт symlink'и в /usr/local/bin,
# либо используется собранный john-jumbo из ~/.local/john/run)
JOHN_RUN_CANDIDATES = [
    "/usr/local/bin",                       # symlink'и из install.sh
    os.path.expanduser("~/.local/john/run"),# собранный jumbo
    "/opt/john/run",                        # альтернативное расположение
]


def _find_tool(tool: str) -> Optional[str]:
    """Найти *2john утилиту в PATH или в известных расположениях john-jumbo."""
    # 1. В PATH (включая /usr/local/bin)
    p = shutil.which(tool)
    if p:
        return p
    # 2. В каталогах john-jumbo
    for d in JOHN_RUN_CANDIDATES:
        candidate = os.path.join(d, tool)
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
        # .py вариант (office2john.py и т.п.)
        candidate_py = os.path.join(d, tool + ".py")
        if os.path.isfile(candidate_py):
            return candidate_py
    return None


def _run_john_tool(tool: str, target: str) -> Optional[str]:
    """Запустить *2john утилиту и вернуть первую строку хэша."""
    path = _find_tool(tool)
    if not path:
        return None
    try:
        # office2john.py и подобные пишут хэш на stdout
        result = subprocess.run(
            [path, target],
            capture_output=True, text=True, timeout=60,
        )
        out = result.stdout.strip()
        if not out:
            return None
        # Берём первую непустую строку (может быть "filename:$hash$")
        for line in out.splitlines():
            line = line.strip()
            if line and not line.startswith("File "):
                # Убираем префикс имени файла если есть
                if ":" in line and line.startswith(target):
                    line = line[len(target):].lstrip(":")
                return line
        return out.splitlines()[0].strip()
    except Exception as e:
        print(f"[!] Ошибка запуска {tool}: {e}", file=sys.stderr)
        return None


# ---------------------------------------------------------------------------
# Встроенный экстрактор для MS Office (fallback, если office2john недоступен)
# ---------------------------------------------------------------------------

def _extract_office_builtin(path: str, info: FormatInfo) -> Optional[str]:
    """Извлечь хэш Office 2007/2010/2013 в формате $office$* без внешних утилит."""
    try:
        import olefile
    except ImportError:
        return None

    try:
        ole = olefile.OleFileIO(path)
        if not ole.exists("EncryptionInfo"):
            ole.close()
            return None
        ei = ole.openstream("EncryptionInfo").read()
        ole.close()
    except Exception as e:
        print(f"[!] Не удалось прочитать EncryptionInfo: {e}", file=sys.stderr)
        return None

    major = struct.unpack_from("<H", ei, 0)[0]
    minor = struct.unpack_from("<H", ei, 2)[0]

    # --- Agile encryption (v4.4): Office 2010/2013 ---
    if major == 4 and minor == 4:
        idx = ei.find(b"<encryption")
        if idx < 0:
            return None
        xml = ei[idx:].decode("utf-8", errors="ignore")

        # Извлекаем параметры из XML
        import re
        def _attr(tag: str, attr: str) -> Optional[str]:
            m = re.search(rf'<{tag}[^>]*\b{attr}="([^"]+)"', xml)
            return m.group(1) if m else None

        # Для 2010/2013 параметры в <keyData> и <p:encryptedKey>
        spin = _attr("p:encryptedKey", "spinCount") or _attr("encryptedKey", "spinCount")
        key_bits = _attr("p:encryptedKey", "keyBits") or _attr("encryptedKey", "keyBits")
        salt_size = _attr("p:encryptedKey", "saltSize") or _attr("encryptedKey", "saltSize")
        salt = _attr("p:encryptedKey", "saltValue") or _attr("encryptedKey", "saltValue")
        vhi = _attr("p:encryptedKey", "encryptedVerifierHashInput") or _attr("encryptedKey", "encryptedVerifierHashInput")
        vhv = _attr("p:encryptedKey", "encryptedVerifierHashValue") or _attr("encryptedKey", "encryptedVerifierHashValue")

        if not all([spin, key_bits, salt_size, salt, vhi, vhv]):
            return None

        salt_hex = base64.b64decode(salt).hex()
        vhi_hex = base64.b64decode(vhi).hex()
        vhv_hex = base64.b64decode(vhv).hex()

        # Определяем год: SHA512 -> 2013 (mode 9600), иначе 2010 (mode 9500)
        year = "2013" if ("SHA512" in xml or "SHA-512" in xml) else "2010"
        return f"$office$*{year}*{spin}*{key_bits}*{salt_size}*{salt_hex}*{vhi_hex}*{vhv_hex}"

    # --- v2.2 / v3.x: Office <=2003 (ECMA-376 Standard Encryption) ---
    # Формат hashcat: $office$*<2007/2003>*... — для старых используем office2john
    return None


def extract_hash(path: str, info: FormatInfo) -> Optional[str]:
    """Извлечь хэш из файла согласно FormatInfo.

    Сначала пробует *2john утилиту; для Office есть встроенный fallback.
    """
    # 1. Встроенный экстрактор для Office (быстрее, без внешних зависимостей)
    if info.decryptor in ("office", "office_old"):
        h = _extract_office_builtin(path, info)
        if h:
            return h
        # Если встроенный не справился (старые форматы) — через office2john

    # 2. Через *2john утилиту
    h = _run_john_tool(info.john_tool, path)
    if h:
        return h

    print(f"[!] Не удалось извлечь хэш. Утилита {info.john_tool} не найдена.", file=sys.stderr)
    print(f"    Установите John the Ripper Jumbo (см. install.sh).", file=sys.stderr)
    return None
