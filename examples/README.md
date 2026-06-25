# Примеры использования

## Восстановление пароля к Excel-файлу

```bash
# Автоопределение, словарь rockyou + best64.rule
python3 recover.py document.xlsx

# С указанным словарём
python3 recover.py document.xlsx --wordlist my_passwords.txt

# Брутфорс по маске (6 цифр)
python3 recover.py document.xlsx --mask "?d?d?d?d?d?d"

# Брутфорс по маске (4-8 символов, буквы+цифры)
python3 recover.py document.xlsx --mask "?a?a?a?a?a?a?a?a" --increment-max 8
```

## Расшифровка с известным паролем

```bash
# Если пароль вспомнили — расшифровать без перебора
python3 recover.py document.xlsx --password 123459 --decrypt-only

# С указанием выходного файла
python3 recover.py document.xlsx --password 123459 --decrypt-only -o clear.xlsx
```

## Только извлечение хэша (для ручного перебора)

```bash
python3 recover.py document.xlsx --hash-only
# Выведет: $office$*2010*100000*128*16*...
# Можно скопировать в файл и запустить hashcat вручную
```

## PDF

```bash
python3 recover.py secret.pdf
python3 recover.py secret.pdf --wordlist /usr/share/dict/words
```

## Архивы (7z/RAR/ZIP)

```bash
python3 recover.py archive.7z
python3 recover.py archive.rar --mask "?d?d?d?d"
python3 recover.py archive.zip --rule dive.rule
```

## Список поддерживаемых форматов

```bash
python3 recover.py --list-formats
```
