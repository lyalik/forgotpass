# Словари

Словари (wordlists) не включены в репозиторий из-за размера.
Скрипт `install.sh` автоматически скачивает `rockyou.txt` (14M утёкших паролей)
— самый эффективный словарь для восстановления забытых паролей.

## Стандартные пути поиска

`recover.py` ищет словари в следующем порядке:

1. Путь, указанный через `--wordlist`
2. `/usr/share/wordlists/rockyou.txt`
3. `~/rockyou.txt`
4. `./wordlists/rockyou.txt` (в каталоге проекта)
5. `/usr/share/dict/words` (системный словарь, fallback)

## Добавление своих словарей

Положите файлы в этот каталог (`wordlists/`) или укажите путь через `--wordlist`:

```bash
python3 recover.py file.xlsx --wordlist /path/to/my_dict.txt
```

## Рекомендуемые словари

| Словарь | Размер | Описание |
|---------|--------|----------|
| rockyou.txt | 14M | Утёкшие пароли RockYou — стандарт де-факто |
| wordlists/words | 100k+ | Системный словарь (английские слова) |
| HIBP | 600M+ | Have I Been Pwned — самый полный |

## Создание своего словаря

Если помните шаблон пароля, создайте файл с вероятными вариантами:

```bash
cat > my_passwords.txt << 'EOF'
denis
Denis
denis123
Denis123
denis2024
пароль
123456
EOF

python3 recover.py file.xlsx --wordlist my_passwords.txt
```

## Rules (мутации)

Rules-файлы hashcat модифицируют слова из словаря (добавляют цифры, меняют регистр,
leetspeak и т.д.). Стандартные rules лежат в `/usr/share/hashcat/rules/`:

| Rule | Описание |
|------|----------|
| best64.rule | 77 правил — лучший баланс скорость/покрытие |
| dive.rule | ~15k правил — глубокий перебор |
| Incisive-leetspeak.rule | Leetspeak замены (a->@, e->3) |
| generated.rule | Сгенерированные правила |

Использование:

```bash
python3 recover.py file.xlsx --rule dive.rule
python3 recover.py file.xlsx --rule none  # без мутаций
```
