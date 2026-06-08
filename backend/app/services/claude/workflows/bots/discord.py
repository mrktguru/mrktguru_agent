from .._types import WorkflowDef, register

register(WorkflowDef(
    id="discord_bot",
    task_type="new_bot",
    label="Discord-бот",
    keywords=["discord", "discord.py", "discord bot", "discord сервер"],
    credits_min=1200,
    credits_max=2000,
    key_pause="после slash-команд и интентов — подтверди необходимые permissions",
    questionnaire=(
        "1. Slash-команды или prefix-команды?\n"
        "2. Функционал: модерация, музыка, RPG, утилиты?\n"
        "3. Нужна ли БД для хранения данных пользователей?\n"
        "4. Интеграции с внешними API?\n"
        "5. Хостинг: VPS, Railway, Repl.it?"
    ),
    phases=(
        "1. Структура + intents + slash-команды (пауза)\n"
        "2. Логика команд и событий\n"
        "3. БД-слой (если нужен)\n"
        "4. Деплой"
    ),
    verification="Пригласить бота на тестовый сервер → все slash-команды работают",
    upsell=["Dashboard для настройки", "Система уровней", "Интеграция с Twitch"],
    spec_hint="Зафиксируй: тип команд, функционал, нужна ли БД.",
))
