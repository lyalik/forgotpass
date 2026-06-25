"""Расшифровка файлов по найденному паролю.

Каждый тип файла расшифровывается соответствующим инструментом:
    - Office (новый, OOXML):  msoffcrypto-tool (Python)
    - Office (старый, OLE2):  msoffcrypto-tool (Python)
    - PDF:                    qpdf (внешняя утилита)
    - 7-Zip:                  7z (внешняя утилита)
    - RAR:                    unrar (внешняя утилита)
    - ZIP:                    7z / unzip (внешняя утилита)
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from typing import Optional


def _check_tool(name: str) -> bool:
    return shutil.which(name) is not None


def _run(cmd: list[str]) -> tuple[int, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        return r.returncode, r.stdout + r.stderr
    except Exception as e:
        return 1, str(e)


# ---------------------------------------------------------------------------
# Office (OOXML 2007+ и старый OLE2)
# ---------------------------------------------------------------------------

def decrypt_office(src: str, password: str, dst: str) -> bool:
    """Расшифровать Office-файл через msoffcrypto-tool."""
    try:
        import msoffcrypto
    except ImportError:
        print("[!] Не установлен msoffcrypto-tool. Установите: pip install msoffcrypto-tool", file=sys.stderr)
        return False
    try:
        with open(src, "rb") as f, open(dst, "wb") as out:
            office = msoffcrypto.OfficeFile(f)
            office.load_key(password=password)
            office.decrypt(out)
        return True
    except Exception as e:
        print(f"[!] Ошибка расшифровки Office: {e}", file=sys.stderr)
        return False


def decrypt_office_old(src: str, password: str, dst: str) -> bool:
    """Старые Office-форматы (<=2003) — тот же msoffcrypto."""
    return decrypt_office(src, password, dst)


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------

def decrypt_pdf(src: str, password: str, dst: str) -> bool:
    """Расшифровать PDF через qpdf."""
    if not _check_tool("qpdf"):
        # fallback: pdftk
        if _check_tool("pdftk"):
            code, out = _run(["pdftk", src, "input_pw", password, "output", dst])
            return code == 0
        print("[!] Не найден qpdf или pdftk. Установите: sudo apt install qpdf", file=sys.stderr)
        return False
    code, out = _run(["qpdf", "--password=" + password, "--decrypt", src, dst])
    if code != 0:
        print(f"[!] Ошибка qpdf: {out}", file=sys.stderr)
    return code == 0


# ---------------------------------------------------------------------------
# 7-Zip
# ---------------------------------------------------------------------------

def decrypt_sevenzip(src: str, password: str, dst_dir: str) -> bool:
    """Извлечь 7z-архив с паролем в каталог dst_dir."""
    tool = "7z" if _check_tool("7z") else ("7za" if _check_tool("7za") else None)
    if not tool:
        print("[!] Не установлен 7z. Установите: sudo apt install p7zip-full", file=sys.stderr)
        return False
    os.makedirs(dst_dir, exist_ok=True)
    code, out = _run([tool, "x", f"-p{password}", "-o" + dst_dir, "-y", src])
    if code != 0:
        print(f"[!] Ошибка 7z: {out}", file=sys.stderr)
    return code == 0


# ---------------------------------------------------------------------------
# RAR
# ---------------------------------------------------------------------------

def decrypt_rar(src: str, password: str, dst_dir: str) -> bool:
    """Извлечь RAR-архив с паролем."""
    if not _check_tool("unrar"):
        print("[!] Не установлен unrar. Установите: sudo apt install unrar", file=sys.stderr)
        return False
    os.makedirs(dst_dir, exist_ok=True)
    code, out = _run(["unrar", "x", f"-p{password}", "-o+", src, dst_dir + "/"])
    if code != 0:
        print(f"[!] Ошибка unrar: {out}", file=sys.stderr)
    return code == 0


# ---------------------------------------------------------------------------
# ZIP
# ---------------------------------------------------------------------------

def decrypt_zip(src: str, password: str, dst_dir: str) -> bool:
    """Извлечь ZIP-архив с паролем."""
    # Предпочитаем 7z (поддерживает WinZip AES), fallback на unzip
    if _check_tool("7z"):
        os.makedirs(dst_dir, exist_ok=True)
        code, out = _run(["7z", "x", f"-p{password}", "-o" + dst_dir, "-y", src])
        if code == 0:
            return True
        print(f"[!] 7z не справился: {out}", file=sys.stderr)
    if _check_tool("unzip"):
        os.makedirs(dst_dir, exist_ok=True)
        code, out = _run(["unzip", "-o", "-P", password, src, "-d", dst_dir])
        if code == 0:
            return True
        print(f"[!] unzip не справился: {out}", file=sys.stderr)
    print("[!] Не найден 7z или unzip. Установите: sudo apt install p7zip-full unzip", file=sys.stderr)
    return False


# ---------------------------------------------------------------------------
# Диспетчер
# ---------------------------------------------------------------------------

DECRYPTORS = {
    "office":      decrypt_office,
    "office_old":  decrypt_office_old,
    "pdf":         decrypt_pdf,
    "sevenzip":    decrypt_sevenzip,
    "rar":         decrypt_rar,
    "zip":         decrypt_zip,
}


def decrypt(src: str, password: str, dst: str, decryptor: str) -> bool:
    """Расшифровать файл указанным расшифровщиком.

    Для архивов dst трактуется как каталог назначения.
    Для Office/PDF dst — путь к выходному файлу.
    """
    fn = DECRYPTORS.get(decryptor)
    if not fn:
        print(f"[!] Неизвестный расшифровщик: {decryptor}", file=sys.stderr)
        return False
    return fn(src, password, dst)
