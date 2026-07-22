#!/usr/bin/env bash
# AgriGuard Easy Runner - No repeated pip installs!

set -e

echo "🚀 AgriGuard Launcher"

# Pick python3 if available, fall back to python
PYTHON_BIN="python3"
command -v python3 >/dev/null 2>&1 || PYTHON_BIN="python"

# Cross-platform sha256
sha256() {
    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum "$1" | awk '{print $1}'
    else
        shasum -a 256 "$1" | awk '{print $1}'
    fi
}

# Virtual env
if [ ! -d ".venv" ]; then
    echo "→ Creating virtual environment..."
    "$PYTHON_BIN" -m venv .venv
fi

source .venv/bin/activate

# Smart dependency install (hash lives INSIDE .venv so a deleted venv forces reinstall)
if [ -f "requirements.txt" ]; then
    HASH_FILE=".venv/.requirements.hash"
    CURRENT_HASH=$(sha256 requirements.txt)

    if [ ! -f "$HASH_FILE" ] || [ "$(cat "$HASH_FILE")" != "$CURRENT_HASH" ]; then
        echo "→ Installing dependencies (one-time or after changes)..."
        pip install --upgrade pip
        pip install -r requirements.txt
        echo "$CURRENT_HASH" > "$HASH_FILE"
    else
        echo "✅ Dependencies up to date."
    fi
fi

# Env file
if [ -f "config/env.example" ] && [ ! -f "config/.env" ]; then
    cp config/env.example config/.env
    echo "⚠️  Created config/.env — edit it with your DB/API keys!"
fi

# Optional full setup
if [[ "$1" == "--setup" || "$1" == "-s" ]]; then
    echo "→ Running data & model setup..."
    [ -f "scripts/download_wfp_data.py" ] && python scripts/download_wfp_data.py
    [ -f "scripts/train_models.py" ] && python scripts/train_models.py
fi

echo "✅ Ready!"
echo "Dashboard → http://localhost:8501"
echo "API docs  → http://localhost:8000/docs"

# Launch — prefer v2 'docker compose', fall back to v1 'docker-compose'
if docker compose version >/dev/null 2>&1; then
    echo "🐳 Starting with Docker Compose (v2)..."
    docker compose up --build
elif command -v docker-compose >/dev/null 2>&1; then
    echo "🐳 Starting with Docker Compose (v1)..."
    docker-compose up --build
else
    echo "💡 Docker not found. Start manually in two terminals:"
    echo "   Terminal 1: uvicorn backend.app.main:app --reload --port 8000"
    echo "   Terminal 2: cd frontend && streamlit run Home.py --server.port 8501"
fi
