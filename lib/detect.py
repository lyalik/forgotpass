"""Определение типа защищённого файла и маппинг на параметры hashcat.

Каждый формат описывается структурой FormatInfo:
    - ext:           ожидаемое расширение (для подсказки)
    - hashcat_mode:  числовой режим hashcat
    - john_tool:     утилита *2john из jumbo для извлечения хэша
    - decryptor:     имя расшифровщика в lib/decrypt.py
    - description:   человекочитаемое описание
"""
from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import Optional


@dataclass
class FormatInfo:
    name: str
    ext: str
    hashcat_mode: int
    john_tool: str
    decryptor: str
    description: str


# Таблица поддерживаемых форматов.
# Порядок важен: более специфичные сигнатуры — раньше.
SUPPORTED: list[FormatInfo] = [
    FormatInfo("MS Office 2007",        "docx/xlsx/pptx", 9400,  "office2john",     "office",   "Word/Excel/PowerPoint 2007 (SHA1+AES-128)"),
    FormatInfo("MS Office 2010",        "docx/xlsx/pptx", 9500,  "office2john",     "office",   "Word/Excel/PowerPoint 2010 (SHA1+AES-128, 100k iter)"),
    FormatInfo("MS Office 2013",        "docx/xlsx/pptx", 9600,  "office2john",     "office",   "Word/Excel/PowerPoint 2013 (SHA512+AES-256)"),
    FormatInfo("MS Office 2016 SheetProt","xlsx",         25300, "office2john",     "office",   "Excel 2016 Sheet Protection"),
    FormatInfo("MS Office <=2003 (MD5)","doc/xls/ppt",    9700,  "office2john",     "office_old","Word/Excel/PowerPoint <=2003 (MD5+RC4)"),
    FormatInfo("MS Office <=2003 (SHA1)","doc/xls/ppt",   9800,  "office2john",     "office_old","Word/Excel/PowerPoint <=2003 (SHA1+RC4)"),
    FormatInfo("PDF 1.1-1.3",           "pdf",            10400, "pdf2john",        "pdf",      "PDF 1.1-1.3 (RC4 40-bit)"),
    FormatInfo("PDF 1.4-1.6",           "pdf",            10500, "pdf2john",        "pdf",      "PDF 1.4-1.6 (RC4 128-bit)"),
    FormatInfo("PDF 1.7 Level 3",       "pdf",            10600, "pdf2john",        "pdf",      "PDF 1.7 Level 3 (AES-128)"),
    FormatInfo("PDF 1.7 Level 8",       "pdf",            10700, "pdf2john",        "pdf",      "PDF 1.7 Level 8 / Acrobat X (AES-256)"),
    FormatInfo("PDF 1.7 Level 8 (new)", "pdf",            10700, "pdf2john",        "pdf",      "PDF 1.7 Level 8 / Acrobat XI (AES-256, new)"),
    FormatInfo("7-Zip",                 "7z",             11600, "7z2john",         "sevenzip", "7-Zip архив"),
    FormatInfo("RAR3-hp",               "rar",            12500, "rar2john",        "rar",      "RAR3 (header encryption)"),
    FormatInfo("RAR5",                  "rar",            13000, "rar2john",        "rar",      "RAR5 архив"),
    FormatInfo("ZIP (PKZIP)",           "zip",            17200, "zip2john",        "zip",      "ZIP/PKZIP архив"),
    FormatInfo("ZIP (WinZip)",          "zip",            13600, "zip2john",        "zip",      "WinZip архив"),
]


def _read_header(path: str, n: int = 512) -> bytes:
    with open(path, "rb") as f:
        return f.read(n)


def _is_ole2(header: bytes) -> bool:
    """Microsoft Compound Document (OLE2) — старый формат Office + OLE-контейнер для новых."""
    return header[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"


def _is_ooxml(path: str) -> bool:
    """OOXML (xlsx/docx/pptx) — это ZIP с определёнными внутренними файлами.
    Зашифрованный OOXML хранится в OLE2-контейнере (EncryptedPackage)."""
    header = _read_header(path, 8)
    if _is_ole2(header):
        # Проверим наличие EncryptionInfo / EncryptedPackage через olefile
        try:
            import olefile
            ole = olefile.OleFileIO(path)
            has_enc = ole.exists("EncryptionInfo") or ole.exists("EncryptedPackage")
            ole.close()
            return has_enc
        except Exception:
            return False
    return False


def _detect_office_year(path: str) -> Optional[FormatInfo]:
    """Точное определение версии Office по EncryptionInfo."""
    try:
        import olefile
        ole = olefile.OleFileIO(path)
        if not ole.exists("EncryptionInfo"):
            ole.close()
            return None
        data = ole.openstream("EncryptionInfo").read()
        ole.close()
        # Версия: 2 байта major + 2 байта minor (little-endian) в начале
        if len(data) < 4:
            return None
        major = struct.unpack_from("<H", data, 0)[0]
        minor = struct.unpack_from("<H", data, 2)[0]
        # v2.2 — RC4 40-bit (Office <=2003, MD5)
        # v3.x — RC4 (Office <=2003, SHA1)
        # v4.x — Agile (XML): 4.4 = Office 2010 (SHA1), 4.4 с SHA512 = 2013
        if major == 2 and minor == 2:
            return SUPPORTED[4]  # MS Office <=2003 (MD5)
        if major == 3 or (major == 4 and minor < 4):
            return SUPPORTED[5]  # MS Office <=2003 (SHA1)
        if major == 4 and minor == 4:
            # Agile: парсим XML, чтобы отличить 2010 (SHA1) от 2013 (SHA512)
            idx = data.find(b"<encryption")
            xml = data[idx:].decode("utf-8", errors="ignore")
            if "SHA512" in xml or "SHA-512" in xml:
                return SUPPORTED[2]  # 2013
            if "SHA1" in xml or "SHA-1" in xml:
                return SUPPORTED[1]  # 2010
            return SUPPORTED[1]  # по умолчанию 2010
        return SUPPORTED[1]
    except Exception:
        return None


def _detect_pdf(header: bytes) -> Optional[FormatInfo]:
    if not header.startswith(b"%PDF-"):
        return None
    # Точную версию (RC4/AES/битность) определит pdf2john + hashcat autodetect.
    # Отдаём 10600 как наиболее общий; hashcat сам уточнит через autodetect.
    return SUPPORTED[7]  # PDF 1.4-1.6 как fallback; autodetect поправит


def _detect_archive(header: bytes) -> Optional[FormatInfo]:
    # 7z: 37 7A BC AF 27 1C
    if header[:6] == b"\x37\x7a\xbc\xaf\x27\x1c":
        return SUPPORTED[11]  # 7-Zip
    # RAR5: 52 61 72 21 1A 07 01 00
    if header[:8] == b"Rar!\x1a\x07\x01\x00":
        return SUPPORTED[13]  # RAR5
    # RAR3: 52 61 72 21 1A 07 00
    if header[:7] == b"Rar!\x1a\x07\x00":
        return SUPPORTED[12]  # RAR3-hp
    # ZIP: 50 4B 03 04 / 50 4B 05 06 / 50 4B 07 08
    if header[:4] in (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"):
        return SUPPORTED[14]  # ZIP (PKZIP) — WinZip уточнится через zip2john
    return None


def detect(path: str) -> Optional[FormatInfo]:
    """Определить формат файла и вернуть FormatInfo или None."""
    header = _read_header(path, 16)

    # 1. Office (OLE2-контейнер с шифрованием)
    if _is_ole2(header):
        info = _detect_office_year(path)
        if info:
            return info
        # OLE2 без шифрования — не наш случай
        return None

    # 2. PDF
    info = _detect_pdf(header)
    if info:
        return info

    # 3. Архивы (7z/RAR/ZIP)
    info = _detect_archive(header)
    if info:
        return info

    return None


def list_supported() -> None:
    """Вывести таблицу поддерживаемых форматов."""
    print(f"{'Формат':<28} {'Расширение':<16} {'hashcat':<8} {'Описание'}")
    print("-" * 90)
    for f in SUPPORTED:
        print(f"{f.name:<28} {f.ext:<16} {f.hashcat_mode:<8} {f.description}")
