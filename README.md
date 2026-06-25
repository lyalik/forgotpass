# forgotpass

> Инструмент восстановления забытых паролей к защищённым файлам.

Автоматически определяет формат файла, извлекает хэш, подбирает пароль через
hashcat и расшифровывает файл. Поддерживает MS Office, PDF, 7-Zip, RAR, ZIP.

## Возможности

- **Автоопределение формата** по сигнатуре файла (не по расширению)
- **Поддерживаемые форматы:**
  - MS Office 2007 / 2010 / 2013 / 2016 (`.xlsx`, `.docx`, `.pptx`, `.xls`, `.doc`)
  - PDF 1.1–1.7 (RC4 40/128-bit, AES-128, AES-256)
  - 7-Zip (`.7z`)
  - RAR3 / RAR5 (`.rar`)
  - ZIP / WinZip (`.zip`)
- **Два режима атаки:**
  - Словарь + rules (rockyou.txt + best64.rule по умолчанию)
  - Брутфорс по маске (`--mask "?d?d?d?d?d?d"`)
- **Расшифровка** найденным паролем в один клик
- **Работает на CPU** (GPU опционально через hashcat)

## Быстрый старт

```bash
# 1. Клонировать (rockyou.txt уже внутри — работает офлайн)
git clone https://github.com/lyalik/forgotpass.git
cd forgotpass

# 2. Установить зависимости (hashcat, Python-пакеты, утилиты)
./install.sh

# 3. Восстановить пароль
python3 recover.py /path/to/file.xlsx
```

## Требования

- Linux (Ubuntu/Debian; на других дистрибутивах замените `apt` в `install.sh`)
- Python 3.10+
- `sudo` для установки системных пакетов
- ~500 МБ свободного места (John the Ripper + rockyou.txt)

## Установка

### Автоматическая (рекомендуется)

```bash
./install.sh
```

Скрипт установит:
| Компонент | Назначение |
|-----------|------------|
| hashcat | Перебор паролей (CPU/GPU) |
| John the Ripper Jumbo | Утилиты `*2john` для извлечения хэшей |
| msoffcrypto-tool, olefile | Расшифровка Office (Python) |
| openpyxl, pypdf | Чтение расшифрованных Office/PDF |
| qpdf | Расшифровка PDF |
| p7zip-full, unrar, unzip | Расшифровка архивов |
| rockyou.txt | Встроенный словарь (top-75, ~59k паролей) — работает офлайн |

### Без сборки John (быстрая установка)

Если нужны только Office-файлы (встроенный экстрактор не требует John):

```bash
./install.sh --no-john
```

### Полная версия словаря (опционально)

Встроенный `rockyou.txt` (top-75, ~59k паролей) покрывает большинство случаев
и работает офлайн. Для сложных паролей можно скачать полную версию (14M паролей, 133MB):

```bash
./install.sh --full-rockyou
```

### Вручную

```bash
sudo apt install hashcat qpdf p7zip-full unrar unzip python3-pip
pip install --user --break-system-packages msoffcrypto-tool olefile openpyxl pypdf
# rockyou.txt уже в репозитории (wordlists/rockyou.txt)
```

## Использование

### Базовый запуск

```bash
python3 recover.py file.xlsx
```

Инструмент:
1. Определит формат (MS Office 2010)
2. Извлечёт хэш (`$office$*2010*...`)
3. Запустит hashcat (rockyou.txt + best64.rule)
4. Расшифрует файл в `file_decrypted.xlsx`

### Все опции

```
python3 recover.py <файл> [опции]

Опции:
  -w, --wordlist PATH       Словарь для атаки
  --rule NAME               Rules-файл hashcat (по умолч. best64.rule, "none" — без rules)
  -m, --mask MASK           Брутфорс по маске (?d — цифра, ?l — буква, ?a — любой)
  --increment-min N         Мин. длина для маски (по умолч. 1)
  --increment-max N         Макс. длина для маски (по умолч. 8)
  --no-increment            Только указанная длина маски
  -p, --password PASS       Расшифровать с известным паролем
  --decrypt-only            Только расшифровка (требует --password)
  -o, --output PATH         Выходной файл
  --hash-only               Только извлечь хэш, без перебора
  --no-decrypt              Найти пароль, но не расшифровывать
  --list-formats            Показать поддерживаемые форматы
```

### Примеры

```bash
# Excel со стандартным словарём
python3 recover.py document.xlsx

# PDF со своим словарём
python3 recover.py secret.pdf --wordlist my_passwords.txt

# 7z, брутфорс 6 цифр
python3 recover.py archive.7z --mask "?d?d?d?d?d?d"

# RAR, глубокие rules
python3 recover.py archive.rar --rule dive.rule

# Известный пароль — только расшифровка
python3 recover.py file.xlsx --password 123459 --decrypt-only

# Только хэш (для ручного hashcat)
python3 recover.py file.xlsx --hash-only

# Список форматов
python3 recover.py --list-formats
```

### Маски hashcat

| Плейсхолдер | Значение |
|-------------|----------|
| `?d` | цифры (0-9) |
| `?l` | строчные буквы (a-z) |
| `?u` | заглавные буквы (A-Z) |
| `?a` | буквы + цифры (a-zA-Z0-9) |
| `?s` | спецсимволы (!@#$...) |
| `?b` | любой байт (0x00-0xff) |

Примеры масок:
- `?d?d?d?d` — 4 цифры (PIN-код, год)
- `?l?l?l?l?d?d` — 4 буквы + 2 цифры
- `?a?a?a?a?a?a?a?a` — 8 любых символов

## Как это работает

```
file.xlsx  ──►  detect()  ──►  FormatInfo(MS Office 2010, mode 9500)
                                    │
                                    ▼
                              extract_hash()  ──►  $office$*2010*100000*...
                                    │
                                    ▼
                              hashcat -m 9500  ──►  пароль: 123459
                                    │
                                    ▼
                              decrypt()  ──►  file_decrypted.xlsx
```

1. **detect** — читает сигнатуру файла (OLE2/ZIP/PDF/RAR/7z), для Office
   парсит `EncryptionInfo` для точного определения версии (2007/2010/2013).
2. **extract** — извлекает хэш в формате hashcat. Для Office используется
   встроенный Python-экстрактор; для PDF/архивов — утилиты `*2john` из
   John the Ripper Jumbo.
3. **crack** — запускает hashcat с хэшем (работает в 25–100× быстрее
   расшифровки каждого файла). Словарь + rules или маска.
4. **decrypt** — расшифровывает файл найденным паролем соответствующим
   инструментом (msoffcrypto / qpdf / 7z / unrar / unzip).

## Производительность

| Формат | hashcat mode | Скорость (CPU 6 ядер) | rockyou (14M) |
|--------|-------------|----------------------|---------------|
| MS Office 2010 | 9500 | ~2200 H/s | ~1.7 часа |
| MS Office 2013 | 9600 | ~500 H/s | ~7 часов |
| PDF 1.7 L8 | 10700 | ~1500 H/s | ~2.5 часа |
| 7-Zip | 11600 | ~50 H/s | ~3 дней |
| ZIP | 17200 | ~50000 H/s | ~5 мин |

С GPU (например RTX 3060) скорость вырастает в 100–1000×.

## Структура проекта

```
forgotpass/
├── recover.py              # Точка входа (CLI)
├── install.sh              # Установка зависимостей
├── requirements.txt        # Python-зависимости
├── lib/
│   ├── detect.py           # Определение формата → hashcat mode
│   ├── extract.py          # Извлечение хэша (*2john / встроенный)
│   ├── crack.py            # Запуск hashcat (wordlist / mask)
│   └── decrypt.py          # Расшифровка по паролю
├── wordlists/
│   └── README.md           # Инструкция по словарям
├── examples/
│   └── README.md           # Примеры использования
├── LICENSE
└── README.md
```

## Ограничения

- **Только для своих файлов.** Инструмент предназначен для восстановления
  доступа к собственным файлам с забытым паролем.
- Сильные пароли (12+ случайных символов) практически не подбираются
  даже с GPU — в этом случае инструмент не поможет.
- Для 7-Zip с AES-256 скорость перебора низкая (~50 H/s на CPU).
- `install.sh` рассчитан на Debian/Ubuntu. Для Fedora/Arch замените
  `apt-get` на соответствующий пакетный менеджер.

## Лицензия

MIT — см. [LICENSE](LICENSE).
