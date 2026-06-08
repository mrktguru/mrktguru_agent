# SiteDoc — AI-разработчик для вашего сайта
## Полная спецификация для реализации

> Этот документ — единственный источник правды для реализации.
> Следуй ему при реализации каждого модуля.
> Версия 2.0 — полностью переработана с учётом всех обсуждений.

---

## 🎯 Суть продукта

**SiteDoc** — AI-агент который дорабатывает существующие сайты без программиста.
Владелец сайта даёт SSH доступ к хостингу, описывает что хочет изменить (или показывает
скриншот) — агент сам разбирается в коде, делает правки и деплоит.

**Фаза 1 (MVP): SiteDoc** — правки и доработки существующих сайтов
**Фаза 2: AppForge** — создание новых приложений с нуля (добавляется позже)

### Целевые пользователи
1. **Владелец сайта-визитки** — нетехнический, правки простые (цвет, текст, шрифт, фото),
   таких миллионы, конверсия высокая
2. **Владелец интернет-магазина** — чуть сложнее, правки функциональные,
   платит больше, каждый клиент ценнее

### Ключевое обещание
> "Кликни что хочешь изменить — AI применит на сервере"

### Конкурентное преимущество
- Фриланс биржи: 3 дня поиска + переписка + риск
- Webflow/Elementor: только для их платформ
- SiteDoc: любой существующий сайт, любой стек, 14 секунд от клика до деплоя

---

## 🏗️ Архитектура платформы

### Три компонента продукта

```
1. Chrome/Firefox расширение   ← визуальный редактор поверх сайта
2. Веб-платформа (SaaS)        ← дашборд, аудит, история правок
3. AI агент + SSH движок       ← мозг и руки системы
```

### Технический стек

**Frontend (веб-платформа)**
- Next.js 14 (App Router), TypeScript
- Mobile-first, PWA
- Tailwind CSS
- Recharts — графики аптайма, статистика токенов
- React DnD — канбан бэклог
- WebSocket — стриминг логов правок в реальном времени

**Browser Extension**
- Chrome Extension Manifest V3 (совместим с Firefox)
- interact.js — drag & drop элементов на странице
- Pickr — color picker
- content_script.js — внедряется на страницу пользователя
- background.js — связь с SiteDoc API через WebSocket

**Backend**
- FastAPI (Python 3.11+)
- Celery + Redis — очередь задач (правки, аудит, мониторинг)
- Paramiko — SSH подключение к хостингу пользователя
- cryptography (Fernet) — шифрование SSH credentials
- WebSocket — стриминг логов клиенту

**База данных**
- PostgreSQL 15+ — основная БД
- pgvector — ML база паттернов правок

**AI**
- Anthropic Claude API (claude-sonnet-4-20250514)
- Claude Vision — распознавание дизайна из скриншотов
- Prompt Caching — обязательно, снижает расходы на 77%
- Одна модель, без выбора для пользователя

**Инфраструктура**
- Docker Compose — платформа SiteDoc
- Проекты пользователей — НЕ в Docker (существующие сайты на их серверах)

---

## 📁 Структура репозитория

```
sitedoc/
├── extension/                        # Chrome/Firefox расширение
│   ├── manifest.json                 # Manifest V3
│   ├── content/
│   │   ├── content_script.js         # Внедряется на страницу
│   │   ├── overlay.js                # Visual overlay поверх сайта
│   │   ├── inspector.js              # Клик → панель редактирования
│   │   ├── drag_drop.js              # Перемещение элементов
│   │   └── diff_collector.js         # Сбор изменений для отправки
│   ├── popup/
│   │   ├── popup.html                # Иконка в браузере
│   │   └── popup.js
│   ├── background/
│   │   └── background.js             # Связь с SiteDoc API
│   └── styles/
│       └── overlay.css               # Стили панели редактирования
│
├── frontend/                         # Next.js платформа
│   ├── app/
│   │   ├── (auth)/
│   │   │   ├── login/
│   │   │   └── register/
│   │   ├── dashboard/                # Список сайтов
│   │   ├── site/
│   │   │   ├── connect/              # Подключение нового сайта
│   │   │   └── [id]/
│   │   │       ├── audit/            # Результаты аудита
│   │   │       ├── tasks/            # Бэклог задач
│   │   │       ├── history/          # История правок
│   │   │       └── settings/         # Настройки сайта
│   │   └── billing/                  # Подписка и токены
│   └── components/
│       ├── audit/
│       │   ├── AuditReport.tsx       # Полный отчёт аудита
│       │   ├── IssueCard.tsx         # Карточка проблемы с кнопкой
│       │   └── SeverityBadge.tsx
│       ├── tasks/
│       │   ├── KanbanBoard.tsx       # Канбан бэклог
│       │   └── TaskCard.tsx
│       ├── editor/
│       │   ├── ChatInput.tsx         # Текстовое описание правки
│       │   ├── ScreenshotUpload.tsx  # Загрузка скриншота
│       │   ├── ChangePreview.tsx     # Превью до/после
│       │   └── TokenEstimate.tsx     # Оценка стоимости в кредитах
│       └── dashboard/
│           ├── SiteCard.tsx          # Карточка сайта
│           └── TokenBalance.tsx      # Баланс токен-кредитов
│
├── backend/                          # FastAPI
│   ├── app/
│   │   ├── api/
│   │   │   ├── auth.py
│   │   │   ├── sites.py              # CRUD сайтов
│   │   │   ├── tasks.py              # Задачи и правки
│   │   │   ├── audit.py              # Аудит сайта
│   │   │   ├── extension.py          # API для расширения
│   │   │   └── billing.py            # Токены и подписка
│   │   ├── services/
│   │   │   ├── agent/
│   │   │   │   ├── auditor.py        # Глубокий аудит сайта
│   │   │   │   ├── task_estimator.py # Оценка задачи в токенах
│   │   │   │   ├── task_executor.py  # Выполнение правки
│   │   │   │   ├── auto_fixer.py     # Автономное исправление ошибок
│   │   │   │   └── suggestions.py    # AI предложения улучшений
│   │   │   ├── vision/
│   │   │   │   ├── style_extractor.py  # Извлечение CSS из скриншота
│   │   │   │   ├── font_detector.py    # Определение шрифтов
│   │   │   │   └── color_extractor.py  # Извлечение палитры
│   │   │   ├── ssh/
│   │   │   │   ├── client.py         # Paramiko SSH клиент
│   │   │   │   ├── scanner.py        # Сканирование сервера и сайта
│   │   │   │   ├── backup.py         # Backup перед правкой
│   │   │   │   └── executor.py       # Выполнение команд
│   │   │   ├── cms/
│   │   │   │   ├── detector.py       # Определение CMS
│   │   │   │   ├── wordpress.py      # WordPress-специфичные операции
│   │   │   │   ├── opencart.py       # OpenCart операции
│   │   │   │   └── custom.py         # Самописные сайты
│   │   │   ├── ml/
│   │   │   │   ├── patterns.py       # ML паттерны правок
│   │   │   │   └── embeddings.py     # pgvector операции
│   │   │   └── claude/
│   │   │       ├── client.py         # Anthropic API с кешированием
│   │   │       └── prompts.py        # System prompts
│   │   ├── models/                   # SQLAlchemy модели
│   │   └── tasks/                    # Celery задачи
│   │       ├── audit.py
│   │       ├── execute.py
│   │       └── monitor.py
│   └── alembic/
│
├── docker-compose.yml
└── COPILOT.md
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
    plan VARCHAR DEFAULT 'starter',     -- starter|pro|agency
    token_credits FLOAT DEFAULT 0,      -- текущий баланс кредитов
    token_credits_monthly FLOAT,        -- ежемесячное пополнение по плану
    timezone VARCHAR DEFAULT 'UTC',
    created_at TIMESTAMP DEFAULT NOW()
);

-- Сайты пользователей
CREATE TABLE sites (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    name VARCHAR NOT NULL,
    url VARCHAR NOT NULL,
    -- SSH доступ
    ssh_host VARCHAR NOT NULL,
    ssh_port INT DEFAULT 22,
    ssh_user VARCHAR NOT NULL,
    auth_type VARCHAR NOT NULL,         -- 'password' | 'platform_key'
    encrypted_credentials TEXT,         -- зашифровано Fernet
    -- Результаты сканирования
    cms VARCHAR,                        -- wordpress|opencart|custom|laravel|etc
    cms_version VARCHAR,
    php_version VARCHAR,
    server_os VARCHAR,
    web_server VARCHAR,                 -- nginx|apache
    site_root_path VARCHAR,             -- /var/www/html
    hardware_info JSONB,
    installed_software JSONB,
    file_structure JSONB,               -- карта файлов сайта
    -- Аудит
    last_audit_at TIMESTAMP,
    audit_report JSONB,                 -- полный отчёт последнего аудита
    audit_score INT,                    -- 0-100
    -- Статус
    status VARCHAR DEFAULT 'active',    -- active|error|scanning
    uptime_percent FLOAT DEFAULT 100,
    last_check_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Задачи (правки и доработки)
CREATE TABLE tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    site_id UUID REFERENCES sites(id),
    user_id UUID REFERENCES users(id),
    -- Описание задачи
    title VARCHAR NOT NULL,
    description TEXT,
    source VARCHAR,                     -- user_text|screenshot|extension_click|audit|ml_suggestion
    -- Входные данные
    screenshot_url VARCHAR,             -- если задача из скриншота
    reference_url VARCHAR,              -- если задача из ссылки
    extracted_styles JSONB,             -- CSS извлечённый из скриншота
    extension_diff JSONB,               -- diff от расширения
    -- Оценка
    estimated_credits FLOAT,           -- оценка до выполнения
    actual_credits FLOAT,              -- фактический расход
    estimated_tokens INT,
    actual_tokens INT,
    confidence VARCHAR,                 -- high|medium|low
    -- Выполнение
    status VARCHAR DEFAULT 'pending',   -- pending|estimated|approved|running|done|failed|rolled_back
    priority VARCHAR DEFAULT 'medium',  -- critical|high|medium|low
    -- Backup и rollback
    backup_path VARCHAR,                -- путь к бэкапу на сервере
    changed_files JSONB,                -- список изменённых файлов
    diff_snapshot TEXT,                 -- git diff или текстовый diff
    -- Результат
    preview_screenshot_before VARCHAR,
    preview_screenshot_after VARCHAR,
    error_message TEXT,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Логи выполнения задач
CREATE TABLE task_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID REFERENCES tasks(id),
    step VARCHAR NOT NULL,
    status VARCHAR,                     -- running|success|error
    message TEXT,
    raw_output TEXT,
    tokens_used INT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Транзакции токен-кредитов
CREATE TABLE token_transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    task_id UUID REFERENCES tasks(id),
    type VARCHAR,                       -- charge|refund|purchase|monthly_refill
    credits_delta FLOAT,               -- отрицательное = списание
    credits_balance FLOAT,             -- баланс после транзакции
    description VARCHAR,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ML паттерны правок
CREATE TABLE edit_patterns (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cms VARCHAR,                        -- для какой CMS
    edit_type VARCHAR,                  -- color|font|layout|feature|etc
    description VARCHAR NOT NULL,
    frequency FLOAT DEFAULT 0,         -- как часто встречается
    avg_credits FLOAT,                 -- средняя стоимость
    success_rate FLOAT DEFAULT 1.0,    -- % успешных выполнений
    embedding vector(1536),
    metadata JSONB,
    updated_at TIMESTAMP DEFAULT NOW()
);

-- История аудитов
CREATE TABLE audit_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    site_id UUID REFERENCES sites(id),
    report JSONB NOT NULL,
    score INT,
    issues_critical INT,
    issues_warning INT,
    issues_info INT,
    created_at TIMESTAMP DEFAULT NOW()
);
```

---

## 🔍 Глубокое сканирование сайта

При первом подключении и по запросу агент делает полный аудит.
Результат — структурированный JSON который используется в каждой задаче.

### Что сканируется

```python
# backend/app/services/agent/auditor.py

AUDIT_CHECKS = {
    "security": [
        "ssl_expiry",           # срок SSL сертификата
        "file_permissions",     # файлы с правами 777
        "exposed_configs",      # .env, wp-config.php в публичном доступе
        "outdated_cms",         # устаревшая версия CMS
        "open_phpmyadmin",      # открытый phpMyAdmin
        "directory_listing",    # открытый листинг директорий
    ],
    "performance": [
        "page_load_time",       # скорость загрузки
        "image_optimization",   # несжатые изображения
        "caching_enabled",      # настроено ли кеширование
        "gzip_compression",     # включён ли gzip
        "database_size",        # размер БД
        "log_file_size",        # раздутые логи
    ],
    "seo": [
        "meta_tags_coverage",   # заполненность мета-тегов
        "mobile_adaptation",    # адаптивность на мобиле
        "sitemap_exists",       # наличие sitemap.xml
        "robots_txt",           # наличие robots.txt
        "broken_links",         # битые ссылки
    ],
    "code_quality": [
        "cms_version",          # версия CMS и плагинов
        "inactive_plugins",     # неактивные плагины
        "custom_code_risks",    # рискованные места в кастомном коде
        "hardcoded_styles",     # захардкоженные стили (сложнее менять)
        "database_queries",     # медленные запросы
    ],
    "site_structure": [
        "file_map",             # карта всех файлов
        "template_files",       # файлы шаблонов
        "custom_files",         # кастомные файлы (трогать осторожно)
        "media_library",        # медиафайлы
        "database_tables",      # таблицы БД
    ]
}
```

### Формат отчёта аудита

```json
{
  "score": 67,
  "scanned_at": "ISO timestamp",
  "cms": "wordpress",
  "cms_version": "6.4.1",
  "php_version": "7.4",

  "issues": {
    "critical": [
      {
        "id": "ssl_expiry",
        "title": "SSL сертификат истекает через 12 дней",
        "description": "Сайт станет недоступен для посетителей",
        "auto_fixable": true,
        "fix_label": "Обновить автоматически",
        "estimated_credits": 2
      },
      {
        "id": "php_outdated",
        "title": "PHP 7.4 — устаревшая версия с уязвимостями",
        "auto_fixable": false,
        "fix_label": "Проконсультироваться с агентом"
      }
    ],
    "warning": [
      {
        "id": "page_speed",
        "title": "Скорость загрузки 8.2 сек (норма < 3)",
        "auto_fixable": true,
        "fix_label": "Оптимизировать",
        "estimated_credits": 8
      }
    ],
    "info": [
      {
        "id": "images_unoptimized",
        "title": "47 изображений не сжаты (+40% к скорости)",
        "auto_fixable": true,
        "fix_label": "Сжать все изображения",
        "estimated_credits": 5
      }
    ]
  },

  "site_features": {
    "custom_plugins": ["my-custom-auth"],
    "hardcoded_files": 12,
    "db_size_mb": 2400,
    "media_count": 847,
    "page_count": 34
  },

  "caution_zones": [
    {
      "file": "wp-content/plugins/my-custom-auth/auth.php",
      "reason": "Кастомная логика авторизации — трогать с осторожностью",
      "risk_level": "high"
    }
  ]
}
```

---

## 🎨 Система визуального редактирования (расширение)

### Три режима расширения

**Режим 1: "Указать"** (для нетехнических)
```
Активировал расширение
        ↓
Кликнул на любой элемент сайта
        ↓
Появилась панель справа:
  - Текущие стили элемента
  - Чат: "Что хочешь изменить?"
  - Загрузить скриншот референса
  - Color picker
  - Выбор шрифта
        ↓
Описал или показал что хочет
        ↓
Агент показал превью прямо на странице
        ↓
Нажал "Сохранить" → деплой на сервер
```

**Режим 2: "Перетащить"**
```
Зажал элемент → перетащил
Расширение запомнило позицию
"Сохранить" → агент переписал CSS/HTML
```

**Режим 3: "Инспектор"** (для продвинутых)
```
Навёл на элемент
Видит стили в панели
Меняет слайдерами
Видит результат мгновенно
Сохраняет через агента
```

### Что можно редактировать визуально

**Типографика:**
- Шрифт — выбор из Google Fonts (1400+ шрифтов) с мгновенным превью
- Размер — слайдер или ввод числа (px / rem / %)
- Жирность — thin / regular / medium / bold / black
- Межбуквенный интервал — слайдер
- Межстрочный интервал — слайдер
- Выравнивание — лево / центр / право / justify
- Цвет — color picker с пипеткой
- Стиль — italic / underline / uppercase / strikethrough

**Изображения:**
- Размер — тащи за уголок (пропорционально) или за край (непропорционально)
- Замена — drag & drop нового файла прямо на изображение
- Замена по URL — вставить ссылку
- Обрезка — визуальный crop прямо в браузере
- Оптимизация — кнопка "Сжать" → агент оптимизирует файл на сервере

**Цвета и фоны:**
- Цвет элемента — HEX / RGB / HSL, пипетка с любого места страницы
- Палитра сайта — цвета которые уже используются на сайте
- Фон блока — сплошной / градиент / изображение / прозрачность

**Отступы и размеры:**
- Визуальная CSS box model — тащи стрелки margin/padding прямо на элементе
- Или вводи числа в поля

**Кнопки:**
- Скругление углов — слайдер
- Тень — интенсивность, направление, цвет, размытие
- Обводка — толщина, цвет, стиль (solid/dashed/dotted)
- Hover эффект — что происходит при наведении
- Текст — редактировать двойным кликом

**Расположение:**
- Перемещение секций вверх/вниз (drag & drop)
- Изменение порядка элементов внутри блока
- Скрыть / показать элемент
- Дублировать блок

**Анимации:**
- Появление при скролле — fade in / slide up / zoom in
- Задержка и скорость — слайдеры

### Панель редактирования (UI)

```
┌─────────────────────────────────────┐
│  📝 <h1> Заголовок        [×]       │
│  ─────────────────────────────────  │
│  Шрифт                              │
│  [Montserrat        ▾] [32px ▾]    │
│  [B] [I] [U]  [≡] [≡] [≡]         │
│                                     │
│  Цвет текста  [████] #1A1A2E       │
│                                     │
│  Отступы  ↑[16] ↓[24] ←[0] →[0]  │
│                                     │
│  ─────────────────────────────────  │
│  📎 Скриншот референса              │
│  🔗 Ссылка на сайт                  │
│  💬 Описать текстом...             │
│                                     │
│  💳 Оценка: ~3 кредита             │
│  [Применить ✓]  [Сбросить]         │
└─────────────────────────────────────┘
```

### Как расширение общается с платформой

```javascript
// extension/background/background.js

const SITEDOC_API = "https://api.sitedoc.io";
const ws = new WebSocket(`wss://api.sitedoc.io/ws/extension`);

async function sendTask(taskData) {
  const response = await fetch(`${SITEDOC_API}/api/tasks/from-extension`, {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${await getAuthToken()}`,
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      site_id: taskData.siteId,
      source: "extension_click",
      element_selector: taskData.selector,
      extension_diff: {
        element: taskData.selector,
        selector_path: taskData.fullPath,
        changes: taskData.changes,        // что изменилось
        screenshot_before: taskData.screenshotBefore,
        screenshot_after: taskData.screenshotAfter
      },
      description: taskData.userDescription,
      screenshot_url: taskData.referenceScreenshot
    })
  });
  return response.json();
}

// Получаем статус выполнения через WebSocket
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.type === "task_update") {
    showNotificationOnPage(data.status, data.message);
  }
};
```

---

## 📸 Извлечение дизайна из скриншота (Claude Vision)

```python
# backend/app/services/vision/style_extractor.py

async def extract_styles_from_screenshot(image_bytes: bytes) -> dict:
    """
    Пользователь загрузил скриншот кнопки/элемента с другого сайта.
    Агент извлекает точные CSS стили через Claude Vision.
    """
    import base64

    response = await claude_client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": base64.b64encode(image_bytes).decode()
                    }
                },
                {
                    "type": "text",
                    "text": """Analyze this UI element screenshot and extract exact CSS properties.

                    Return ONLY valid JSON (no markdown, no explanation):
                    {
                      "element_type": "button|card|header|text|image|input|other",
                      "background_color": "#hex or gradient string",
                      "text_color": "#hex",
                      "border_radius": "Npx",
                      "border": "Npx solid #hex or none",
                      "font_size": "Npx",
                      "font_weight": "N00",
                      "font_family": "name or null",
                      "padding": "Npx Npx Npx Npx",
                      "box_shadow": "CSS shadow string or none",
                      "width": "Npx or auto",
                      "height": "Npx or auto",
                      "hover_state": {
                        "background_color": "#hex or null",
                        "transform": "CSS transform or null"
                      },
                      "additional_notes": "any important visual details"
                    }"""
                }
            ]
        }]
    )

    return json.loads(response.content[0].text)


async def extract_font_from_screenshot(image_bytes: bytes) -> dict:
    """Определяем шрифт из скриншота текста"""
    response = await claude_client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=256,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                              "data": base64.b64encode(image_bytes).decode()}},
                {"type": "text", "text": """Identify the font in this screenshot.
                Return JSON only:
                {
                  "font_family": "exact name or closest Google Font match",
                  "font_weight": "N00",
                  "is_google_font": true/false,
                  "confidence": "high|medium|low",
                  "alternatives": ["font1", "font2"]
                }"""}
            ]
        }]
    )
    return json.loads(response.content[0].text)
```

---

## 💰 Токен-кредиты — монетизация

### Концепция

Токен-кредит — абстракция над реальными токенами Claude.
Скрывает техническую деталь, даёт понятную единицу измерения.

```
1 токен-кредит = 10,000 реальных токенов Claude

Реальная стоимость 1 кредита для платформы:
  Input:  8K × $3/1M   = $0.024
  Output: 2K × $15/1M  = $0.030
  Итого без кеша:       = $0.054
  С кешированием (77%): ≈ $0.015

Продаётся пользователю:
  В подписке: ~$0.12-0.20 за кредит
  В пакете:   ~$0.09-0.18 за кредит
  Маржа: 6x — 13x
```

### Стоимость типовых задач

| Задача | Кредитов | Реальная стоимость | Цена для юзера |
|--------|----------|-------------------|----------------|
| Изменить цвет кнопки | 1-2 | $0.015-0.03 | $0.12-0.36 |
| Сменить шрифт | 2-4 | $0.03-0.06 | $0.24-0.72 |
| Добавить форму | 10-20 | $0.15-0.30 | $1.2-3.6 |
| Новая страница | 30-50 | $0.45-0.75 | $3.6-9 |
| Полный аудит | 15-25 | $0.22-0.37 | $1.8-4.5 |
| Оптимизация скорости | 20-40 | $0.30-0.60 | $3.6-7.2 |

### Тарифные планы

```python
PLANS = {
    "starter": {
        "price_usd": 19,
        "credits_monthly": 100,         # ~5-8 простых правок
        "max_sites": 1,
        "audit_on_connect": True,
        "monitoring": "basic",           # ping каждые 10 мин
        "extension_access": True,
        "rollback_days": 7,
    },
    "pro": {
        "price_usd": 49,
        "credits_monthly": 400,         # ~20-30 правок
        "max_sites": 5,
        "audit_on_connect": True,
        "monitoring": "advanced",        # ping + auto-fix
        "extension_access": True,
        "rollback_days": 30,
        "priority_execution": True,
    },
    "agency": {
        "price_usd": 149,
        "credits_monthly": 2000,        # ~100+ правок
        "max_sites": -1,                # unlimited
        "audit_on_connect": True,
        "monitoring": "advanced",
        "extension_access": True,
        "rollback_days": 90,
        "priority_execution": True,
        "white_label": True,
        "api_access": True,
        "client_management": True,      # управление сайтами клиентов
    }
}

# Пакеты докупки кредитов
CREDIT_PACKS = [
    {"credits": 100,  "price_usd": 9,   "per_credit": 0.09},
    {"credits": 500,  "price_usd": 35,  "per_credit": 0.07},
    {"credits": 2000, "price_usd": 99,  "per_credit": 0.049},
]
```

### Оценка задачи до выполнения

```python
# backend/app/services/agent/task_estimator.py

async def estimate_task(
    task_description: str,
    site_context: dict,
    screenshot_styles: dict = None
) -> dict:
    """
    ОБЯЗАТЕЛЬНО вызывается перед каждой задачей.
    Пользователь видит оценку и подтверждает.
    """

    prompt = f"""
    You are estimating the cost of a website edit task.
    
    Task: {task_description}
    Site CMS: {site_context['cms']}
    Site complexity: {site_context['file_count']} files,
                     {site_context['custom_files']} custom files
    Caution zones: {site_context['caution_zones']}
    
    {"Extracted styles from screenshot: " + str(screenshot_styles) if screenshot_styles else ""}
    
    Estimate token usage for completing this task. Consider:
    1. Code analysis needed (reading files to understand context)
    2. Planning the changes
    3. Writing/modifying code
    4. Verification and testing
    
    Return JSON only:
    {{
      "steps": [
        {{"name": "Анализ кода", "tokens": N, "reason": "..."}},
        {{"name": "Внесение изменений", "tokens": N, "reason": "..."}},
        {{"name": "Проверка", "tokens": N, "reason": "..."}}
      ],
      "total_tokens": N,
      "total_credits": N,
      "confidence": "high|medium|low",
      "risk_level": "low|medium|high",
      "risk_reason": "...",
      "estimated_minutes": N
    }}
    """

    response = await claude_client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=512,
        system=[{
            "type": "text",
            "text": "You are a precise cost estimator for website editing tasks.",
            "cache_control": {"type": "ephemeral"}
        }],
        messages=[{"role": "user", "content": prompt}]
    )

    estimate = json.loads(response.content[0].text)

    # Резервируем кредиты до выполнения
    await reserve_credits(user_id, estimate["total_credits"] * 1.2)  # +20% буфер

    return estimate
```

---

## 🔧 Выполнение задачи агентом

```python
# backend/app/services/agent/task_executor.py

class TaskExecutor:

    EXECUTION_STEPS = [
        ("backup",   "Создание резервной копии"),
        ("analyze",  "Анализ кода сайта"),
        ("plan",     "Планирование изменений"),
        ("execute",  "Внесение изменений"),
        ("verify",   "Проверка результата"),
        ("cleanup",  "Завершение"),
    ]

    async def execute(self, task: dict, log_callback) -> dict:
        """
        Полный цикл выполнения задачи.
        log_callback стримит прогресс через WebSocket.
        """
        site = await get_site(task["site_id"])
        ssh = SSHClient(site)
        ssh.connect()

        try:
            # 1. Backup ВСЕГДА первым шагом
            await log_callback("backup", "running", "Создаю резервную копию...")
            backup_path = await self._create_backup(ssh, site, task)
            await log_callback("backup", "success", f"Бэкап создан: {backup_path}")

            # 2. Анализ — читаем нужные файлы
            await log_callback("analyze", "running", "Изучаю код сайта...")
            code_context = await self._analyze_site(ssh, site, task)
            await log_callback("analyze", "success", f"Проанализировано {code_context['files_read']} файлов")

            # 3. Планирование через Claude
            await log_callback("plan", "running", "Планирую изменения...")
            plan = await self._create_plan(task, code_context, site)
            await log_callback("plan", "success", f"План готов: {len(plan['changes'])} изменений")

            # 4. Выполнение
            await log_callback("execute", "running", "Вношу изменения...")
            results = await self._apply_changes(ssh, plan, site)
            await log_callback("execute", "success", "Изменения применены")

            # 5. Проверка
            await log_callback("verify", "running", "Проверяю результат...")
            verified = await self._verify_changes(ssh, site, results)

            if not verified["success"]:
                # Автоматический откат
                await self._rollback(ssh, backup_path)
                await log_callback("verify", "error", "Ошибка — откатываю изменения")
                return {"success": False, "rolled_back": True}

            await log_callback("verify", "success", "✓ Всё работает")

            # Скриншот после
            screenshot_after = await self._take_screenshot(site["url"])

            return {
                "success": True,
                "changed_files": results["changed_files"],
                "backup_path": backup_path,
                "screenshot_after": screenshot_after,
                "actual_tokens": results["tokens_used"]
            }

        except Exception as e:
            # При любой ошибке — откатываем
            await self._rollback(ssh, backup_path)
            await log_callback("error", "error", f"Ошибка исправлена — изменения откатаны")
            raise

    async def _create_plan(self, task: dict, code_context: dict, site: dict) -> dict:
        """Claude анализирует задачу и планирует конкретные изменения"""

        response = await claude_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=[
                {
                    "type": "text",
                    "text": f"""You are an expert web developer modifying an existing website.
                    CMS: {site['cms']} {site['cms_version']}
                    PHP: {site['php_version']}
                    Caution zones: {site['audit_report']['caution_zones']}
                    
                    Rules:
                    - NEVER modify caution zone files without explicit confirmation
                    - Always consider mobile responsiveness
                    - Preserve existing functionality
                    - Make minimal necessary changes
                    - If changing font, add Google Fonts CDN link to <head>
                    """,
                    "cache_control": {"type": "ephemeral"}
                },
                {
                    "type": "text",
                    "text": f"SITE CODE CONTEXT:\n{code_context['relevant_files']}",
                    "cache_control": {"type": "ephemeral"}
                }
            ],
            messages=[{
                "role": "user",
                "content": f"""Task: {task['description']}
                
                {"Extracted CSS from reference screenshot: " + str(task.get('extracted_styles')) if task.get('extracted_styles') else ""}
                {"Extension diff: " + str(task.get('extension_diff')) if task.get('extension_diff') else ""}
                
                Plan the exact file changes needed. Return JSON:
                {{
                  "changes": [
                    {{
                      "file": "relative/path/to/file.css",
                      "type": "modify|create",
                      "find": "exact string to find",
                      "replace": "exact replacement string",
                      "description": "human readable description"
                    }}
                  ],
                  "new_files": [],
                  "shell_commands": [],
                  "verification_steps": ["how to verify the change worked"]
                }}"""
            }]
        )

        return json.loads(response.content[0].text)
```

---

## 🔄 Полный воркфлоу — от клика до деплоя

```
ВАРИАНТ А: Через расширение

10:00:00  Пользователь кликнул на кнопку на своём сайте
10:00:01  Появилась панель редактирования расширения
10:00:03  Загрузил скриншот кнопки с другого сайта
10:00:04  Claude Vision извлёк CSS стили из скриншота
10:00:05  Агент оценил задачу: ~3 кредита, ~2 минуты
10:00:07  Пользователь нажал "Применить"
10:00:07  Резервируются кредиты
10:00:08  Backup файлов на сервере
10:00:09  Агент читает нужные файлы по SSH
10:00:11  Claude планирует изменения
10:00:13  Изменения применяются на сервере
10:00:14  Автоматическая проверка
10:00:14  ✓ "Готово" — кредиты списаны фактически


ВАРИАНТ Б: Через чат на платформе

Пользователь пишет: "Сделай кнопку 'Купить' синей"
        ↓
Агент: "Оцениваю задачу... ~2 кредита"
        ↓
[Подтвердить] → выполнение → готово


ВАРИАНТ В: Из списка аудита

Аудит нашёл: "SSL истекает через 12 дней"
Пользователь нажимает: [Обновить автоматически]
        ↓
Агент выполняет без дополнительных вопросов
```

---

## 🧠 Prompt Caching — обязательно

```python
# backend/app/services/claude/client.py

async def call_agent_with_cache(
    task: str,
    site_context: dict,
    relevant_files: str,
    conversation_history: list
) -> dict:

    response = await anthropic_client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        system=[
            # Кешируем system prompt (статичный)
            {
                "type": "text",
                "text": TASK_EXECUTION_SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"}
            },
            # Кешируем контекст сайта (меняется редко)
            {
                "type": "text",
                "text": f"SITE CONTEXT:\n{json.dumps(site_context)}",
                "cache_control": {"type": "ephemeral"}
            },
            # Кешируем код файлов сайта (большой, статичный в рамках задачи)
            {
                "type": "text",
                "text": f"SITE FILES:\n{relevant_files}",
                "cache_control": {"type": "ephemeral"}
            }
        ],
        # НЕ кешируем — динамическое
        messages=conversation_history
    )

    # Логируем экономию
    cache_savings = (
        response.usage.cache_read_input_tokens * 0.9 * 3 / 1_000_000
    )

    return {
        "content": response.content[0].text,
        "tokens_used": response.usage.input_tokens + response.usage.output_tokens,
        "cache_savings_usd": cache_savings
    }
```

---

## 🛡️ Безопасность и Rollback

```python
# backend/app/services/ssh/backup.py

class BackupManager:

    async def create_backup(self, ssh: SSHClient, site: dict, task_id: str) -> str:
        """
        Backup создаётся ПЕРЕД каждой правкой.
        Пользователь может откатить из интерфейса.
        """
        backup_dir = f"/tmp/sitedoc_backups/{task_id}"

        # Определяем какие файлы трогаем
        affected_files = await self._predict_affected_files(site, task_id)

        commands = [
            f"mkdir -p {backup_dir}",
            # Копируем только нужные файлы, не весь сайт
            *[f"cp {f} {backup_dir}/" for f in affected_files],
            f"echo '{json.dumps(affected_files)}' > {backup_dir}/manifest.json",
            f"echo '{datetime.utcnow().isoformat()}' > {backup_dir}/timestamp"
        ]

        for cmd in commands:
            async for _ in ssh.execute_stream(cmd):
                pass

        return backup_dir

    async def rollback(self, ssh: SSHClient, backup_path: str) -> bool:
        """Мгновенный откат к состоянию до правки"""
        manifest = json.loads(
            await ssh.read_file(f"{backup_path}/manifest.json")
        )

        for original_path in manifest:
            filename = original_path.split("/")[-1]
            await ssh.execute(f"cp {backup_path}/{filename} {original_path}")

        return True
```

---

## 📡 WebSocket — стриминг прогресса

```python
# backend/app/api/tasks.py

@router.websocket("/ws/task/{task_id}")
async def task_websocket(websocket: WebSocket, task_id: str):
    await websocket.accept()

    async def log_callback(step: str, status: str, message: str):
        await websocket.send_json({
            "type": "task_log",
            "step": step,
            "status": status,       # running|success|error
            "message": message,
            "timestamp": datetime.utcnow().isoformat()
        })

    # Задача выполняется в Celery (фоново)
    # Пользователь может закрыть браузер — выполнение продолжится
    task = execute_task.delay(task_id)

    # Стримим логи из Redis
    pubsub = redis.pubsub()
    pubsub.subscribe(f"task_logs:{task_id}")

    while not task.ready():
        message = pubsub.get_message()
        if message and message["type"] == "message":
            await websocket.send_json(json.loads(message["data"]))
        await asyncio.sleep(0.2)

    await websocket.send_json({"type": "task_complete"})
```

---

## 🔄 Мониторинг сайтов

```python
# backend/app/tasks/monitor.py

@celery.task
def monitor_all_sites():
    """Каждые 5 минут через celery beat"""
    sites = get_all_active_sites()

    for site in sites:
        try:
            is_alive = check_site_health(site["url"])
            update_uptime(site["id"], is_alive)

            if not is_alive:
                # Пробуем перезапустить веб-сервер
                restarted = restart_web_server(site)

                if not restarted:
                    # Агент анализирует логи
                    fix_result = auto_fix_site(site)

                    if not fix_result["success"]:
                        # Уведомляем пользователя понятным языком
                        notify_user(
                            site["user_id"],
                            f"Сайт {site['url']} временно недоступен. Мы уже разбираемся."
                        )
        except Exception as e:
            log_error(site["id"], str(e))
```

---

## 🛣️ Роадмап реализации

### MVP — SiteDoc (2-3 месяца)
1. Аутентификация (email + Google OAuth)
2. Подключение сайта по SSH (пароль + ключ платформы)
3. Глубокое сканирование + аудит
4. Задачи через текстовый чат
5. Claude Vision — задачи из скриншота
6. Оценка в токен-кредитах перед выполнением
7. Backup + rollback
8. Живой лог выполнения через WebSocket
9. Базовый мониторинг
10. Billing — подписка + докупка кредитов

### Версия 2 — Расширение (3-4 месяц)
11. Chrome расширение — базовый инспектор
12. Визуальный color picker и typography panel
13. Drag & drop элементов
14. Мгновенный превью изменений в браузере
15. Google Fonts интегрирован в расширение
16. Канбан бэклог задач

### Версия 3 — ML + оптимизация (5-6 месяц)
17. ML паттерны — предложения из опыта других сайтов
18. Автоматические предложения из аудита
19. White label для агентств
20. API доступ

### Версия 4 — AppForge (6+ месяц)
21. Режим "создать с нуля" — 4 фазы проектирования
22. Визуализации фаз (mind map, feature board, flow diagram)
23. Деплой новых проектов в Docker на VPS
24. Интерактивный прототип перед деплоем

---

## ⚙️ Переменные окружения

```env
# Anthropic
ANTHROPIC_API_KEY=sk-ant-...

# Database
DATABASE_URL=postgresql://user:pass@postgres:5432/sitedoc

# Redis
REDIS_URL=redis://redis:6379/0

# Security
SECRET_KEY=...                        # JWT
FERNET_KEY=...                        # SSH credentials encryption
PLATFORM_SSH_KEY_PATH=/app/keys/platform_key

# App
FRONTEND_URL=https://sitedoc.io
EXTENSION_ID=chrome-extension-id
ENVIRONMENT=production

# Stripe
STRIPE_SECRET_KEY=sk_...
STRIPE_WEBHOOK_SECRET=whsec_...
```

---

## 📝 Ключевые принципы реализации

1. **Backup всегда первым** — перед любой правкой создаётся резервная копия затрагиваемых файлов. Rollback доступен из интерфейса.

2. **Оценка до выполнения** — пользователь всегда видит сколько кредитов спишется ПЕРЕД тем как нажать "Применить". Никаких сюрпризов.

3. **Кеширование обязательно** — system prompt, контекст сайта и код файлов кешируются через `cache_control: {"type": "ephemeral"}`. Без этого расходы на токены в 3-4 раза выше.

4. **Превью перед деплоем** — изменение показывается пользователю (скриншот до/после или превью в расширении) до применения на реальный сервер.

5. **Агент читает глубоко** — перед правкой агент изучает весь контекст: CMS, структуру файлов, caution zones, связанные файлы. Не делает слепых изменений.

6. **Caution zones** — файлы помеченные при аудите как рискованные никогда не трогаются без явного подтверждения пользователя.

7. **Пользователь не видит ошибок** — при сбое агент откатывает изменения и показывает "исправлено" или "не удалось выполнить". Никаких stack trace.

8. **ML учится на каждой задаче** — после выполнения задача записывается в паттерны: тип правки, CMS, сколько токенов ушло, успешно ли. База растёт и улучшает оценки.

9. **Расширение = превью, платформа = деплой** — расширение показывает изменения мгновенно через JS injection (временно, не реально). Реальный деплой только после подтверждения через платформу.

10. **Docker для платформы, не для сайтов пользователей** — SiteDoc сам работает в Docker. Сайты пользователей — существующие, агент работает с ними как есть через SSH.
