# AppForge — AI App Builder
## Полная спецификация для реализации

> Этот документ описывает полную архитектуру, функционал и логику платформы.
> Следуй ему при реализации каждого модуля.

---

## 🎯 Суть продукта

Веб-платформа (mobile-first) где **нетехнический человек** описывает идею приложения,
отвечает на простые вопросы агента, даёт SSH доступ к своему VPS —
и получает работающее задеплоенное приложение. Без кода, без терминала, без DevOps.

**Целевой пользователь:** человек с идеей и VPS, без технических знаний.
**Ключевое обещание:** от идеи до работающего приложения — только через диалог.

---

## 🏗️ Технический стек платформы

### Frontend
- **Next.js 14** (App Router), TypeScript
- **Mobile-first**, PWA (работает как приложение на телефоне)
- **React Flow** — интерактивные флоу-диаграммы и архитектурные схемы
- **D3.js** — mind maps, графы
- **React DnD** — drag & drop для бэклога и карточек функций
- **Recharts** — графики аптайма и активности
- **Tailwind CSS** — стилизация
- **WebSocket** (native) — стриминг логов деплоя в реальном времени

### Backend
- **FastAPI** (Python 3.11+)
- **Celery + Redis** — очередь фоновых задач (деплои, мониторинг)
- **Paramiko** — SSH подключение и выполнение команд на VPS
- **cryptography (Fernet)** — шифрование SSH credentials
- **WebSocket** — стриминг логов клиенту

### База данных
- **PostgreSQL 15+** — основная БД
- **pgvector** — расширение для ML базы знаний (semantic search)

### AI
- **Anthropic Claude API** (claude-sonnet-4-20250514) — основная модель
- **Prompt Caching** — обязательно для всех статичных блоков контекста
- Модель одна — не давай пользователю выбор модели (нетехническая аудитория)

### Инфраструктура платформы
- **Docker Compose** — локальная разработка и продакшн платформы
- Сервисы: app (FastAPI), worker (Celery), redis, postgres, nginx

### Деплой проектов пользователей
- Каждый проект пользователя — **изолированный Docker контейнер** на его VPS
- Никогда не устанавливай ничего напрямую на хост — только через Docker
- Docker Compose файл генерируется агентом под каждый проект

---

## 📁 Структура репозитория

```
appforge/
├── frontend/                    # Next.js приложение
│   ├── app/
│   │   ├── (auth)/
│   │   │   ├── login/
│   │   │   └── register/
│   │   ├── dashboard/           # Главный дашборд
│   │   ├── project/
│   │   │   ├── new/             # Создание проекта (4 фазы)
│   │   │   └── [id]/            # Страница проекта
│   │   └── settings/
│   ├── components/
│   │   ├── agent/               # Чат-интерфейс агента
│   │   ├── viz/                 # Все визуализации
│   │   │   ├── MindMap.tsx      # D3 mind map (фаза 1)
│   │   │   ├── FeatureBoard.tsx # Карточки функций (фаза 2)
│   │   │   ├── FlowDiagram.tsx  # React Flow (фаза 3)
│   │   │   ├── ArchDiagram.tsx  # Архитектурная схема (фаза 3)
│   │   │   └── DeployLog.tsx    # Живой лог деплоя (фаза 4)
│   │   ├── backlog/             # Канбан бэклог
│   │   └── dashboard/           # Карточки проектов
│   └── lib/
│       ├── api.ts               # API клиент
│       └── websocket.ts         # WebSocket клиент
│
├── backend/                     # FastAPI приложение
│   ├── app/
│   │   ├── api/
│   │   │   ├── auth.py
│   │   │   ├── projects.py
│   │   │   ├── servers.py
│   │   │   ├── agent.py         # Эндпоинты агента
│   │   │   └── backlog.py
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   ├── security.py      # JWT, шифрование
│   │   │   └── database.py
│   │   ├── services/
│   │   │   ├── agent/
│   │   │   │   ├── phases.py    # Логика 4 фаз
│   │   │   │   ├── questions.py # Адаптивные вопросы
│   │   │   │   ├── spec.py      # JSON спецификация
│   │   │   │   └── suggestions.py # ML suggestions
│   │   │   ├── ssh/
│   │   │   │   ├── client.py    # Paramiko SSH клиент
│   │   │   │   ├── scanner.py   # Сканирование сервера
│   │   │   │   └── executor.py  # Выполнение команд
│   │   │   ├── deploy/
│   │   │   │   ├── generator.py # Генерация кода и конфигов
│   │   │   │   ├── deployer.py  # Деплой на VPS
│   │   │   │   └── monitor.py   # Мониторинг проектов
│   │   │   ├── ml/
│   │   │   │   ├── knowledge.py # ML база знаний
│   │   │   │   └── embeddings.py # pgvector операции
│   │   │   └── claude/
│   │   │       ├── client.py    # Anthropic API клиент с кешированием
│   │   │       └── prompts.py   # System prompts всех фаз
│   │   ├── models/              # SQLAlchemy модели
│   │   └── tasks/               # Celery задачи
│   │       ├── deploy.py
│   │       └── monitor.py
│   └── alembic/                 # Миграции БД
│
├── docker-compose.yml           # Платформа
└── COPILOT.md                   # Этот файл
```

---

## 🗄️ Схема базы данных

```sql
-- Пользователи
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR UNIQUE NOT NULL,
    password_hash VARCHAR,
    google_id VARCHAR,
    name VARCHAR,
    timezone VARCHAR DEFAULT 'UTC',
    created_at TIMESTAMP DEFAULT NOW()
);

-- Серверы пользователей
CREATE TABLE servers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    name VARCHAR NOT NULL,
    ip VARCHAR NOT NULL,
    ssh_user VARCHAR NOT NULL,
    -- credentials хранятся зашифрованно через Fernet
    auth_type VARCHAR NOT NULL, -- 'password' | 'platform_key'
    encrypted_credentials TEXT, -- зашифрованный JSON
    os_info JSONB,              -- результат сканирования
    hardware_info JSONB,
    installed_software JSONB,
    status VARCHAR DEFAULT 'active',
    created_at TIMESTAMP DEFAULT NOW()
);

-- Проекты
CREATE TABLE projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    server_id UUID REFERENCES servers(id),
    name VARCHAR NOT NULL,
    type VARCHAR[],             -- ['telegram_bot', 'web_app', etc.]
    status VARCHAR DEFAULT 'draft', -- draft|building|deployed|error
    current_phase INT DEFAULT 1, -- 1-4
    spec JSONB,                 -- финальная JSON спецификация
    conversation_history JSONB, -- история диалога с агентом
    deploy_path VARCHAR,        -- путь на VPS
    domain VARCHAR,
    admin_url VARCHAR,
    uptime_percent FLOAT,
    last_active_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    deployed_at TIMESTAMP
);

-- Задачи бэклога
CREATE TABLE backlog_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id),
    title VARCHAR NOT NULL,
    description TEXT,
    priority VARCHAR DEFAULT 'medium', -- critical|high|medium|low
    effort VARCHAR,             -- small|medium|large
    status VARCHAR DEFAULT 'backlog', -- backlog|in_progress|done
    source VARCHAR,             -- user|agent_suggestion|phase_2|ml_pattern
    phase VARCHAR,              -- mvp|post_mvp|future
    accepted BOOLEAN,
    position INT,               -- для drag & drop порядка
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Логи деплоя
CREATE TABLE deploy_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id),
    step VARCHAR NOT NULL,
    status VARCHAR,             -- pending|running|success|error
    message TEXT,
    raw_output TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ML база знаний
CREATE TABLE ml_patterns (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_type VARCHAR[],
    feature VARCHAR NOT NULL,
    frequency FLOAT DEFAULT 0,      -- как часто встречается
    usually_requested BOOLEAN,      -- пользователь просил сам
    usually_added_later BOOLEAN,    -- добавляли после деплоя
    accepted_count INT DEFAULT 0,   -- сколько раз приняли suggestion
    rejected_count INT DEFAULT 0,   -- сколько раз отклонили
    embedding vector(1536),         -- pgvector embedding
    metadata JSONB,
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Пресеты стеков по типу проекта
CREATE TABLE stack_presets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_type VARCHAR NOT NULL,
    stack JSONB NOT NULL,
    success_rate FLOAT,
    common_errors JSONB,
    updated_at TIMESTAMP DEFAULT NOW()
);
```

---

## 🤖 JSON спецификация проекта

Это центральный объект — агент заполняет его через все 4 фазы.
К фазе 4 он должен быть полным. Пустые поля заполняются допущениями агента.

```json
{
  "meta": {
    "project_id": "uuid",
    "name": "Название проекта",
    "created_at": "ISO timestamp",
    "phase_completed": 3
  },

  "idea": {
    "problem": "Какую проблему решаем",
    "target_user": "Кто пользователь",
    "current_solution": "Что делает сейчас без продукта",
    "type": ["telegram_bot", "web_app", "parser", "landing"],
    "similar_projects_ids": ["uuid1", "uuid2"]
  },

  "product": {
    "personas": {
      "end_user": {
        "description": "Описание конечного пользователя",
        "goals": ["цель 1", "цель 2"],
        "pain_points": ["боль 1"],
        "main_flow": ["шаг 1", "шаг 2", "шаг 3"]
      },
      "admin": {
        "description": "Владелец продукта",
        "goals": ["управление контентом", "просмотр статистики"],
        "features": ["список пользователей", "статистика", "настройки"]
      }
    },
    "features": {
      "mvp": [
        {"id": "f1", "title": "Название", "description": "Описание", "source": "user|ml_pattern"}
      ],
      "post_mvp": [],
      "future": []
    },
    "constraints": {
      "budget": null,
      "timeline": null,
      "technical": []
    }
  },

  "workflow": {
    "user_flow": [
      {"step": 1, "action": "Открыл бота", "next": [2]},
      {"step": 2, "action": "Выбрал услугу", "next": [3, 4]}
    ],
    "admin_flow": [
      {"step": 1, "action": "Зашёл в админку", "next": [2]}
    ],
    "stack": {
      "language": "Python",
      "framework": "aiogram",
      "database": "PostgreSQL",
      "infrastructure": "Docker",
      "additional": ["Redis", "Celery"]
    },
    "components": [
      {"name": "Telegram Bot", "role": "Интерфейс пользователя", "port": 8080},
      {"name": "FastAPI Backend", "role": "Бизнес логика", "port": 8000},
      {"name": "PostgreSQL", "role": "База данных", "port": 5432}
    ],
    "data_model": {},
    "integrations": []
  },

  "assumptions": [
    {
      "field": "check_interval",
      "assumed": "каждые 30 минут",
      "reason": "не было указано пользователем",
      "accepted": null,
      "user_value": null
    }
  ],

  "agent_suggestions": [
    {
      "id": "s1",
      "feature": "Напоминания за день до записи",
      "reason": "87% похожих проектов добавляли это",
      "ml_frequency": 0.87,
      "phase": "mvp",
      "accepted": null
    }
  ],

  "backlog": [
    {
      "title": "Название задачи",
      "priority": "high",
      "effort": "medium",
      "phase": "post_mvp",
      "source": "agent_suggestion"
    }
  ]
}
```

---

## 💬 Логика агента — 4 фазы

### Общие принципы
- Всегда задавай **один вопрос за раз** — никогда не несколько сразу
- Веди себя как **думающий партнёр**, не как анкета
- Отвечай на том же языке что пишет пользователь (RU/EN)
- После каждого ответа пользователя обновляй JSON спецификацию
- Если поле неясно — делай допущение, фиксируй в `assumptions`, не блокируй прогресс

### Промпты по фазам

Все промпты хранятся в `backend/app/services/claude/prompts.py`.
Все статичные блоки промптов маркируются `cache_control: {"type": "ephemeral"}`.

#### ФАЗА 1 — Идея

```python
PHASE_1_SYSTEM = """
You are a Product Discovery expert. Your goal: understand the core idea deeply.

Rules:
- Ask ONE question at a time
- Focus on the PROBLEM, not the solution
- After 3-5 exchanges, when you have a clear picture:
  1. Show a structured summary of the idea
  2. Ask user to confirm
  3. End with [PHASE_COMPLETE: {json_summary}]

Questions to cover (adapt order and wording naturally):
1. Who is the user of this product?
2. What problem are we solving?
3. What does the user do NOW without this product?

Always respond in the user's language (Russian or English).
"""
```

#### ФАЗА 2 — Продукт

```python
PHASE_2_SYSTEM = """
You are a Product Manager defining the product clearly.

Context from Phase 1: {phase_1_summary}
ML patterns for this project type: {ml_patterns}

Your job:
1. Ask conditional questions based on project type:
   - Telegram bot: payments? user registration? commands or Q&A?
   - Web app: user auth? file uploads? external integrations?
   - Parser: frequency? data storage? notifications?

2. Think about TWO personas simultaneously:
   - END USER: what they do in the product
   - ADMIN: how the owner manages the product

3. Apply ML patterns:
   - frequency > 0.8 → add to MVP silently, mention you added it
   - frequency 0.5-0.8 → suggest with explanation
   - frequency < 0.5 → add to backlog as idea

4. Show suggestions with social proof:
   "87% of similar projects added this feature"

5. At the end show three lists: MVP / Post-MVP / Ideas
   Wait for user confirmation.
   End with [PHASE_COMPLETE: {features_json}]

Always ONE question at a time. Respond in user's language.
"""
```

#### ФАЗА 3 — Воркфлоу

```python
PHASE_3_SYSTEM = """
You are a Systems Architect designing how the product works.

Context:
- Phase 1: {phase_1_summary}
- Phase 2: {phase_2_summary}
- Server info: {server_info}

Your job:
1. Map out user flow step by step (for both end user AND admin)
2. Choose optimal tech stack based on project type:
   - Telegram bot → Python + aiogram + PostgreSQL + Docker
   - Web app → FastAPI + PostgreSQL + Nginx + SSL + Docker
   - Landing → Nginx + static or Next.js + Docker
   - Parser → Python + schedule/celery + PostgreSQL + Docker
3. Define components and how they interact
4. Fill unknown fields with reasonable assumptions
5. Show assumptions separately: "I made these assumptions — please check"

Output at end:
- Architecture in simple words (no tech jargon for user)
- List of assumptions with [Confirm] / [Change] buttons
- End with [PHASE_COMPLETE: {full_spec_json}]

Respond in user's language.
"""
```

#### ФАЗА 4 — Деплой

```python
PHASE_4_SYSTEM = """
You are a Senior Developer who knows this project completely.

Full specification: {full_spec_json}
Server info: {server_info}

Generate production-ready code:
1. Main application (end user facing)
2. Admin panel (owner facing) at /admin route
3. Docker Compose file (ALWAYS use Docker, never install directly on host)
4. Nginx config
5. SSL via Let's Encrypt (certbot)
6. .env template with all required variables

Code requirements:
- Clean, well-commented
- Error handling for all edge cases
- Logging configured
- Health check endpoint
- Graceful shutdown

Return structured JSON:
{
  "files": [
    {"path": "relative/path/file.py", "content": "..."},
    ...
  ],
  "deploy_commands": ["command1", "command2"],
  "env_variables": [{"key": "BOT_TOKEN", "description": "Telegram bot token"}]
}
"""
```

---

## 🔌 Реализация Prompt Caching

**КРИТИЧНО:** кешируй все статичные блоки. Это снижает расход токенов на 77%.

```python
# backend/app/services/claude/client.py

import anthropic
from .prompts import get_phase_system_prompt

client = anthropic.Anthropic()

async def call_agent(
    phase: int,
    conversation_history: list,
    context: dict
) -> dict:
    
    system_prompt = get_phase_system_prompt(phase, context)
    ml_context = context.get("ml_patterns", "")
    project_spec = context.get("current_spec", "")
    
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        system=[
            # Кешируем system prompt фазы (статичный, большой)
            {
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"}
            },
            # Кешируем ML паттерны (меняются редко)
            {
                "type": "text",
                "text": f"ML PATTERNS:\n{ml_context}",
                "cache_control": {"type": "ephemeral"}
            },
            # Кешируем накопленную спецификацию
            {
                "type": "text",
                "text": f"CURRENT SPEC:\n{project_spec}",
                "cache_control": {"type": "ephemeral"}
            }
        ],
        # НЕ кешируем — история диалога (динамическая)
        messages=conversation_history
    )
    
    # Логируем использование кеша для мониторинга расходов
    usage = response.usage
    cache_savings = usage.cache_read_input_tokens * 0.9  # 90% дешевле
    
    return {
        "content": response.content[0].text,
        "usage": {
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
            "cache_read_tokens": usage.cache_read_input_tokens,
            "cache_write_tokens": usage.cache_creation_input_tokens,
            "estimated_savings_usd": cache_savings * 3 / 1_000_000
        }
    }
```

---

## 🖥️ SSH агент

```python
# backend/app/services/ssh/client.py

import paramiko
import asyncio
from cryptography.fernet import Fernet
from typing import AsyncGenerator

class SSHClient:
    
    def __init__(self, server: dict, fernet_key: bytes):
        self.server = server
        self.fernet = Fernet(fernet_key)
        self.client = None
    
    def connect(self):
        """Подключение с поддержкой пароля и ключа платформы"""
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        creds = self._decrypt_credentials()
        
        if self.server["auth_type"] == "password":
            self.client.connect(
                hostname=self.server["ip"],
                username=self.server["ssh_user"],
                password=creds["password"],
                timeout=10
            )
        else:  # platform_key
            self.client.connect(
                hostname=self.server["ip"],
                username=self.server["ssh_user"],
                key_filename="/app/keys/platform_key",
                timeout=10
            )
    
    def scan_server(self) -> dict:
        """Сканируем сервер перед деплоем"""
        commands = {
            "os": "lsb_release -d | cut -f2",
            "ram_free": "free -m | awk '/Mem/{print $4}'",
            "disk_free": "df -BG / | awk 'NR==2{print $4}'",
            "docker_version": "docker --version 2>/dev/null || echo 'not installed'",
            "open_ports": "ss -tlnp | awk 'NR>1{print $4}' | grep -oP ':\K\d+'",
        }
        result = {}
        for key, cmd in commands.items():
            _, stdout, _ = self.client.exec_command(cmd)
            result[key] = stdout.read().decode().strip()
        return result
    
    async def execute_stream(self, command: str) -> AsyncGenerator[str, None]:
        """Выполняем команду со стримингом вывода в реальном времени"""
        transport = self.client.get_transport()
        channel = transport.open_session()
        channel.exec_command(command)
        
        while True:
            if channel.recv_ready():
                data = channel.recv(1024).decode("utf-8", errors="replace")
                yield data
            if channel.exit_status_ready():
                break
            await asyncio.sleep(0.1)
    
    def _decrypt_credentials(self) -> dict:
        import json
        decrypted = self.fernet.decrypt(
            self.server["encrypted_credentials"].encode()
        )
        return json.loads(decrypted)
```

---

## 🚀 Деплой проекта

```python
# backend/app/services/deploy/deployer.py

import asyncio
from ..ssh.client import SSHClient
from ..claude.client import call_agent

class ProjectDeployer:
    
    DEPLOY_STEPS = [
        ("prepare", "Подготовка окружения"),
        ("upload", "Загрузка кода"),
        ("build", "Docker build"),
        ("start", "Запуск контейнеров"),
        ("nginx", "Настройка Nginx"),
        ("ssl", "SSL сертификат"),
        ("verify", "Финальная проверка"),
    ]
    
    def __init__(self, project: dict, server: dict, ssh: SSHClient):
        self.project = project
        self.server = server
        self.ssh = ssh
        self.project_dir = f"/opt/appforge/{project['id']}"
    
    async def deploy(self, log_callback):
        """
        Полный цикл деплоя с логированием.
        log_callback(step, status, message) — вызывается на каждом шаге.
        Отправляется клиенту через WebSocket.
        """
        spec = self.project["spec"]
        
        # Генерируем все файлы проекта через Claude
        await log_callback("generate", "running", "Генерирую код проекта...")
        files = await self._generate_code(spec)
        await log_callback("generate", "success", "Код сгенерирован")
        
        for step_id, step_name in self.DEPLOY_STEPS:
            await log_callback(step_id, "running", f"{step_name}...")
            try:
                await getattr(self, f"_step_{step_id}")(files, spec)
                await log_callback(step_id, "success", f"{step_name} ✓")
            except Exception as e:
                await log_callback(step_id, "error", str(e))
                # Пытаемся починить автономно
                fixed = await self._auto_fix(step_id, str(e), spec)
                if fixed:
                    await log_callback(step_id, "success", f"{step_name} ✓ (исправлено)")
                else:
                    raise
    
    async def _auto_fix(self, step: str, error: str, spec: dict) -> bool:
        """Агент анализирует ошибку и пробует починить"""
        fix_prompt = f"""
        Deploy step '{step}' failed with error: {error}
        Project spec: {spec}
        Server info: {self.server['os_info']}
        
        Analyze the error and provide the fix commands to run on the server.
        Return JSON: {{"commands": ["cmd1", "cmd2"], "explanation": "..."}}
        """
        # ... вызов Claude, выполнение fix команд
        return True
    
    async def _step_prepare(self, files, spec):
        cmds = [
            f"mkdir -p {self.project_dir}",
            f"cd {self.project_dir}",
            "docker network create appforge 2>/dev/null || true",
        ]
        for cmd in cmds:
            async for _ in self.ssh.execute_stream(cmd):
                pass
    
    async def _step_build(self, files, spec):
        cmd = f"cd {self.project_dir} && docker compose build --no-cache"
        async for output in self.ssh.execute_stream(cmd):
            pass  # output уже стримится через log_callback
```

---

## 📊 Визуализации — что рендерить на каждой фазе

### Фаза 1 — Mind Map (D3.js)
```typescript
// components/viz/MindMap.tsx
// Строится в реальном времени по мере диалога
// Данные приходят из spec.idea

interface MindMapData {
  center: string        // название идеи
  nodes: {
    id: string
    label: string
    type: 'problem' | 'user' | 'solution' | 'pain'
    filled: boolean     // false = подсвечивается как неясное
  }[]
  edges: { from: string; to: string }[]
}
// Анимация: каждый новый узел появляется с transition
// Пустые узлы: пульсирующая обводка — "ещё не прояснили"
```

### Фаза 2 — Feature Board (drag & drop)
```typescript
// components/viz/FeatureBoard.tsx
// Три колонки: MVP | После MVP | Идеи
// Карточки появляются по ходу диалога
// Suggestions агента: тег "💡 из 43 проектов [87%]"
// Пользователь перетаскивает между колонками

interface FeatureCard {
  id: string
  title: string
  column: 'mvp' | 'post_mvp' | 'future'
  source: 'user' | 'ml_pattern'
  ml_frequency?: number   // показываем если source === 'ml_pattern'
  persona: 'end_user' | 'admin' | 'both'
}
```

### Фаза 3 — Flow + Architecture (React Flow)
```typescript
// components/viz/FlowDiagram.tsx — пользовательский флоу
// components/viz/ArchDiagram.tsx — компонентная схема

// FlowDiagram: узлы = шаги, рёбра = переходы
// Два таба: "Пользователь" / "Админ"
// Строится шаг за шагом пока агент проектирует

// ArchDiagram: компоненты внутри Docker host
// Стрелки = взаимодействие между сервисами
// Порты подписаны

// Допущения — отдельный блок под диаграммами:
// Каждое допущение: текст + [Подтвердить ✓] [Изменить]
```

### Фаза 4 — Deploy Log
```typescript
// components/viz/DeployLog.tsx
// WebSocket подписка на /ws/deploy/{project_id}

interface DeployStep {
  id: string
  name: string
  status: 'pending' | 'running' | 'success' | 'error' | 'fixed'
  message: string
  timestamp: string
}
// Иконки: ○ pending | 🔄 running (анимация) | ✓ success | ⚠️ fixed | ✗ error
// Можно закрыть браузер — деплой продолжится в Celery
// При возврате — подгружаем логи из БД + переподключаемся к WS
```

### Дашборд проекта
```typescript
// Карточка проекта:
// Статус: ● Работает / ⚠️ Проблема / 🔄 Деплоится
// Аптайм за 7 дней: sparkline график (Recharts)
// Последняя активность: "3 мин назад"

// Страница проекта:
// Канбан бэклог: [Критично] [Высокий] [Средний] [Идеи]
// Drag & drop между колонками
// Клик на задачу → "Сделать сейчас" → агент берёт в работу
```

---

## 🧠 ML База знаний

```python
# backend/app/services/ml/knowledge.py

from pgvector.sqlalchemy import Vector
import numpy as np

class MLKnowledgeBase:
    
    async def find_patterns(self, project_type: list, description: str) -> list:
        """
        Semantic search по базе паттернов.
        Вызывается в начале Фазы 1 для загрузки контекста.
        """
        embedding = await self._embed(description)
        
        # pgvector cosine similarity search
        patterns = await db.execute("""
            SELECT *, 1 - (embedding <=> $1) as similarity
            FROM ml_patterns
            WHERE project_type && $2
            AND 1 - (embedding <=> $1) > 0.75
            ORDER BY similarity DESC, frequency DESC
            LIMIT 10
        """, embedding, project_type)
        
        return self._format_for_prompt(patterns)
    
    async def record_project(self, project: dict):
        """
        Вызывается после успешного деплоя.
        Обновляет паттерны на основе результата проекта.
        """
        spec = project["spec"]
        
        for feature in spec["product"]["features"]["mvp"]:
            await self._update_pattern(
                project_type=spec["idea"]["type"],
                feature=feature["title"],
                was_requested=feature["source"] == "user",
                was_suggested=feature["source"] == "ml_pattern",
                was_accepted=True
            )
        
        for suggestion in spec["agent_suggestions"]:
            await self._update_pattern(
                project_type=spec["idea"]["type"],
                feature=suggestion["feature"],
                was_requested=False,
                was_suggested=True,
                was_accepted=suggestion["accepted"] or False
            )
    
    def _format_for_prompt(self, patterns: list) -> str:
        """Форматируем для вставки в system prompt агента"""
        result = []
        for p in patterns:
            threshold = "add_to_mvp_silently" if p.frequency > 0.8 \
                else "suggest" if p.frequency > 0.5 \
                else "add_to_backlog"
            result.append(
                f"- {p.feature}: frequency={p.frequency:.0%}, "
                f"action={threshold}"
            )
        return "\n".join(result)
```

---

## 📡 WebSocket — стриминг деплоя

```python
# backend/app/api/agent.py

from fastapi import WebSocket
import asyncio

@router.websocket("/ws/deploy/{project_id}")
async def deploy_websocket(websocket: WebSocket, project_id: str):
    await websocket.accept()
    
    async def log_callback(step: str, status: str, message: str):
        await websocket.send_json({
            "type": "deploy_log",
            "step": step,
            "status": status,
            "message": message,
            "timestamp": datetime.utcnow().isoformat()
        })
    
    # Запускаем деплой в Celery (фоново)
    task = deploy_project.delay(project_id)
    
    # Стримим логи пока задача выполняется
    while not task.ready():
        logs = await get_new_logs(project_id)
        for log in logs:
            await websocket.send_json(log)
        await asyncio.sleep(0.5)
    
    await websocket.send_json({"type": "deploy_complete"})
```

---

## 🔐 Безопасность

```python
# backend/app/core/security.py

from cryptography.fernet import Fernet
import os

# Ключ шифрования SSH credentials — хранится в env, никогда в коде
FERNET_KEY = os.environ["FERNET_KEY"]  # генерируется один раз: Fernet.generate_key()
fernet = Fernet(FERNET_KEY)

def encrypt_credentials(data: dict) -> str:
    import json
    return fernet.encrypt(json.dumps(data).encode()).decode()

def decrypt_credentials(encrypted: str) -> dict:
    import json
    return json.loads(fernet.decrypt(encrypted.encode()))

# SSH ключ платформы (вариант Б подключения)
# Генерируется один раз при деплое платформы:
# ssh-keygen -t ed25519 -f /app/keys/platform_key -N ""
# Публичный ключ показывается пользователю для добавления на сервер
```

---

## 💰 Тарифы и лимиты

```python
PLANS = {
    "starter": {
        "price_usd": 29,
        "max_projects": 3,
        "deploys_per_month": 10,
        "iterations_per_month": 50,
        "max_servers": 1,
        "monitoring": "basic",      # ping каждые 5 мин
    },
    "pro": {
        "price_usd": 79,
        "max_projects": 10,
        "deploys_per_month": -1,    # unlimited
        "iterations_per_month": -1,
        "max_servers": 3,
        "monitoring": "advanced",   # ping + auto-fix
    },
    "agency": {
        "price_usd": 199,
        "max_projects": -1,
        "deploys_per_month": -1,
        "iterations_per_month": -1,
        "max_servers": -1,
        "monitoring": "advanced",
        "white_label": True,
        "api_access": True,
    }
}
```

---

## 🔄 Мониторинг проектов (фоновый)

```python
# backend/app/tasks/monitor.py

@celery.task
def monitor_all_projects():
    """Запускается каждые 5 минут через celery beat"""
    projects = get_all_deployed_projects()
    
    for project in projects:
        try:
            is_alive = ping_project(project)
            update_uptime(project.id, is_alive)
            
            if not is_alive:
                # Пытаемся перезапустить контейнер
                restarted = restart_container(project)
                
                if not restarted:
                    # Анализируем логи и чиним
                    fixed = auto_fix_project(project)
                    
                    if not fixed:
                        # Уведомляем пользователя простыми словами
                        notify_user(
                            project.user_id,
                            f"Проект '{project.name}' временно недоступен. "
                            f"Мы уже разбираемся."
                        )
        except Exception as e:
            log_monitor_error(project.id, str(e))
```

---

## 🛣️ Роадмап реализации

### MVP (2-3 месяца)
1. Аутентификация + базовый дашборд
2. Подключение VPS (оба метода) + сканирование
3. Фазы 1-3 агента (диалог + JSON спецификация)
4. Генерация кода + деплой Telegram бота (один тип для старта)
5. Живой лог деплоя через WebSocket
6. Базовый мониторинг

### Версия 2 (3-4 месяц)
7. Все типы проектов (web app, landing, parser)
8. Визуализации всех фаз
9. Бэклог с канбаном
10. ML база знаний + suggestions
11. Автономное исправление ошибок
12. Правки проектов через чат

### Версия 3 (5-6 месяц)
13. White label для агентств
14. Маркетплейс шаблонов
15. Managed VPS опция
16. API доступ
17. Advanced мониторинг + аналитика

---

## ⚙️ Переменные окружения

```env
# Anthropic
ANTHROPIC_API_KEY=sk-ant-...

# Database
DATABASE_URL=postgresql://user:pass@postgres:5432/appforge

# Redis
REDIS_URL=redis://redis:6379/0

# Security
SECRET_KEY=...                    # для JWT
FERNET_KEY=...                    # для шифрования SSH credentials
PLATFORM_SSH_KEY_PATH=/app/keys/platform_key

# App
FRONTEND_URL=https://appforge.io
ENVIRONMENT=production
```

---

## 📝 Ключевые принципы реализации

1. **Docker везде** — каждый проект пользователя изолирован в контейнере на его VPS. Никогда не устанавливай ничего напрямую на хост.

2. **Кеширование обязательно** — все статичные блоки промптов (system prompts, ML паттерны, JSON спецификация) должны иметь `cache_control: {"type": "ephemeral"}`. Без этого расходы на токены в 3-4 раза выше.

3. **Один вопрос за раз** — агент никогда не задаёт несколько вопросов одновременно. Это UX принцип для нетехнической аудитории.

4. **Допущения, не блокировки** — если поле неясно, агент делает разумное допущение, фиксирует его в `assumptions` и движется вперёд. Показывает допущения пользователю на подтверждение в конце фазы.

5. **Живая визуализация** — все схемы строятся в реальном времени по мере диалога, не показываются готовыми. Пользователь видит как рождается его продукт.

6. **Двойная персона** — в фазе 2 агент всегда думает о двух ролях: конечный пользователь и админ. Каждый проект деплоится с admin панелью по умолчанию.

7. **ML учится на каждом проекте** — после каждого успешного деплоя `record_project()` должен вызываться обязательно. Это основа умности платформы.

8. **Автономность в технических ошибках** — пользователь никогда не видит stack trace. Видит только "исправляю..." или "готово". Агент чинит сам через `_auto_fix()`.
```
