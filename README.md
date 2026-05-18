# AppForge — AI App Builder

Веб-платформа, где нетехнический пользователь описывает идею приложения через диалог с AI-агентом и получает работающее задеплоенное приложение на своём VPS.

См. полную спецификацию в [COPILOT.md](COPILOT.md).

## 🚀 Быстрый старт

### Требования
- Docker & Docker Compose
- (Опционально) Node 20+ и Python 3.11+ для разработки вне Docker

### Запуск через Docker

```bash
# 1. Скопируй переменные окружения
cp .env.example .env
# 2. Заполни ANTHROPIC_API_KEY, SECRET_KEY, FERNET_KEY в .env
#    SECRET_KEY:  python -c "import secrets; print(secrets.token_urlsafe(64))"
#    FERNET_KEY:  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# 3. Подними платформу
docker compose up -d --build

# 4. Применить миграции БД
docker compose exec backend alembic upgrade head

# 5. Открыть в браузере
# Frontend:  http://localhost:3000
# Backend:   http://localhost:8000/docs
```

## 🏗️ Архитектура

```
appforge/
├── backend/          # FastAPI + Celery + SQLAlchemy
├── frontend/         # Next.js 14 (App Router) + Tailwind
├── docker-compose.yml
└── COPILOT.md        # Полная спецификация
```

### Стек
- **Frontend:** Next.js 14, TypeScript, Tailwind, React Flow, D3.js, WebSocket
- **Backend:** FastAPI, SQLAlchemy 2.0 (async), Celery, Redis
- **AI:** Anthropic Claude (claude-sonnet-4) с prompt caching
- **DB:** PostgreSQL 16 + pgvector
- **Деплой проектов пользователей:** Docker на их VPS через Paramiko

## 🧠 Логика агента (4 фазы)

1. **Фаза 1 — Идея.** Понять проблему и пользователя (mind map).
2. **Фаза 2 — Продукт.** Зафиксировать MVP-фичи (feature board).
3. **Фаза 3 — Воркфлоу.** Спроектировать архитектуру (flow + arch).
4. **Фаза 4 — Деплой.** Сгенерировать код и задеплоить на VPS (live log).

## 🛠️ Разработка

```bash
# Backend локально
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Frontend локально
cd frontend
npm install
npm run dev
```

## 📜 Лицензия

Proprietary. © MrktGuru.
