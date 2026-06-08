from .._types import WorkflowDef, register

register(WorkflowDef(
    id="rest_api",
    task_type="new_site",
    label="REST API / Backend-сервис",
    keywords=["rest api", "fastapi", "swagger", "django rest", "flask api", "express api"],
    credits_min=1500,
    credits_max=2500,
    key_pause="после схемы эндпоинтов и моделей данных — подтверди контракт API",
    questionnaire=(
        "1. Фреймворк: FastAPI, Django DRF, Flask, Express?\n"
        "2. БД: PostgreSQL, MySQL, MongoDB, SQLite?\n"
        "3. Аутентификация: JWT, OAuth2, API-ключи, сессии?\n"
        "4. Список основных сущностей и операций (CRUD)?\n"
        "5. Нужна ли документация Swagger/OpenAPI?"
    ),
    phases=(
        "1. Схема эндпоинтов + модели данных (пауза)\n"
        "2. Маршруты и контроллеры\n"
        "3. Аутентификация + авторизация\n"
        "4. Миграции + seed-данные\n"
        "5. Тесты + Swagger/OpenAPI"
    ),
    verification="Swagger UI → все эндпоинты документированы и работают; auth flow проверен",
    upsell=["Rate limiting", "API versioning", "SDK-клиент"],
    spec_hint="Зафиксируй: фреймворк, БД, список сущностей, тип аутентификации.",
))
