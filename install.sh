#!/usr/bin/env bash
#
# install.sh — установка зависимостей для forgotpass
#
# Устанавливает:
#   - hashcat (перебор паролей, CPU/GPU)
#   - John the Ripper Jumbo (утилиты *2john для извлечения хэшей)
#   - Python-зависимости (msoffcrypto-tool, openpyxl, pypdf, olefile)
#   - Утилиты расшифровки (qpdf, p7zip-full, unrar, unzip)
#   - Словарь rockyou.txt (если отсутствует)
#
# Запуск:
#   ./install.sh           — полная установка
#   ./install.sh --no-john — без сборки John the Ripper (медленнее для не-Office)
#
set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[+]${NC} $1"; }
warn()  { echo -e "${YELLOW}[!]${NC} $1"; }
error() { echo -e "${RED}[!]${NC} $1"; }

# Проверка root
if [ "$EUID" -eq 0 ]; then
    error "Не запускайте от root. Скрипт сам вызовет sudo где нужно."
    exit 1
fi

BUILD_JOHN=true
if [ "$1" = "--no-john" ]; then
    BUILD_JOHN=false
fi

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
JOHN_DIR="$HOME/.local/john"

echo "============================================"
echo "  Установка forgotpass"
echo "============================================"
echo ""

# --- 1. Системные пакеты ---
info "Установка системных пакетов (требуется sudo)..."
sudo apt-get update -qq
sudo apt-get install -y -qq \
    hashcat \
    python3 python3-pip \
    build-essential git wget \
    libssl-dev zlib1g-dev \
    qpdf p7zip-full unrar unzip \
    2>&1 | tail -5

# --- 2. Python-зависимости ---
info "Установка Python-зависимостей..."
pip3 install --user --break-system-packages \
    msoffcrypto-tool \
    olefile \
    openpyxl \
    pypdf \
    2>&1 | tail -3 || warn "Некоторые pip-пакеты не установились (возможно уже есть)."

# --- 3. John the Ripper Jumbo (для *2john утилит) ---
if [ "$BUILD_JOHN" = true ] && [ ! -d "$JOHN_DIR/src" ]; then
    info "Сборка John the Ripper Jumbo (для утилит *2john)..."
    info "Это может занять 5-10 минут..."
    mkdir -p "$HOME/.local"
    cd /tmp
    rm -rf john-jumbo-build
    git clone --depth=1 https://github.com/openwall/john.git john-jumbo-build 2>&1 | tail -2
    cd john-jumbo-build/src
    ./configure --prefix="$JOHN_DIR" 2>&1 | tail -3
    make -j"$(nproc)" 2>&1 | tail -3
    make install 2>&1 | tail -2
    cd "$PROJECT_DIR"
    rm -rf /tmp/john-jumbo-build
    info "John the Ripper установлен в $JOHN_DIR"

    # Создаём symlink'и на *2john в ~/.local/bin
    mkdir -p "$HOME/.local/bin"
    for tool in office2john pdf2john 7z2john rar2john zip2john; do
        src_tool="$JOHN_DIR/run/${tool}"
        # .py вариант
        if [ ! -f "$src_tool" ] && [ -f "$JOHN_DIR/run/${tool}.py" ]; then
            src_tool="$JOHN_DIR/run/${tool}.py"
        fi
        if [ -f "$src_tool" ]; then
            ln -sf "$src_tool" "$HOME/.local/bin/${tool}"
            info "  symlink: ${tool}"
        fi
    done
else
    if [ "$BUILD_JOHN" = true ]; then
        info "John the Ripper уже собран в $JOHN_DIR — пропуск."
    else
        warn "Сборка John пропущена (--no-john). Извлечение хэшей для PDF/архивов будет недоступно."
        warn "Office-файлы работают без John (встроенный экстрактор)."
    fi
fi

# --- 4. Словарь rockyou.txt ---
ROCKYOU="$PROJECT_DIR/wordlists/rockyou.txt"
if [ ! -f "$ROCKYOU" ] || [ ! -s "$ROCKYOU" ]; then
    info "Загрузка словаря rockyou.txt..."
    mkdir -p "$PROJECT_DIR/wordlists"
    wget -q --timeout=60 \
        "https://github.com/brannondorsey/naive-hashcat/releases/download/data/rockyou.txt" \
        -O "$ROCKYOU" 2>&1 || warn "Не удалось скачать rockyou.txt. Скачайте вручную."
    if [ -s "$ROCKYOU" ]; then
        info "rockyou.txt загружен ($(wc -l < "$ROCKYOU") строк)"
    fi
else
    info "rockyou.txt уже есть ($(wc -l < "$ROCKYOU") строк)"
fi

# --- 5. Проверка ---
echo ""
echo "============================================"
info "Проверка установки:"
echo "============================================"
check() {
    if command -v "$1" &>/dev/null || [ -x "$HOME/.local/bin/$1" ]; then
        echo -e "  ${GREEN}✓${NC} $1"
    else
        echo -e "  ${RED}✗${NC} $1"
    fi
}
check hashcat
check office2john
check pdf2john
check 7z2john
check rar2john
check zip2john
check qpdf
check 7z
check unrar
check unzip
python3 -c "import msoffcrypto" 2>/dev/null && echo -e "  ${GREEN}✓${NC} msoffcrypto (py)" || echo -e "  ${YELLOW}~${NC} msoffcrypto (py) — только для Office"
python3 -c "import olefile" 2>/dev/null && echo -e "  ${GREEN}✓${NC} olefile (py)" || echo -e "  ${RED}✗${NC} olefile (py)"

echo ""
info "Установка завершена!"
echo ""
echo "  Использование:"
echo "    python3 $PROJECT_DIR/recover.py <файл>"
echo "    python3 $PROJECT_DIR/recover.py --list-formats"
echo ""
echo "  ВАЖНО: добавьте ~/.local/bin в PATH, если ещё не добавили:"
echo "    echo 'export PATH=\$HOME/.local/bin:\$PATH' >> ~/.bashrc && source ~/.bashrc"
echo ""
