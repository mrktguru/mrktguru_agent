from .._types import WorkflowDef, register

register(WorkflowDef(
    id="telegram_bot",
    task_type="new_bot",
    label="Telegram-бот",
    keywords=["telegram", "телеграм", "aiogram", "telegram bot", "telebot"],
    credits_min=800,
    credits_max=3000,
    key_pause="после FSM-схемы и списка команд — подтверди сценарии диалога",
    questionnaire=(
        "1. Команды и основные сценарии бота?\n"
        "2. Нужна ли БД (пользователи, данные)? Какая?\n"
        "3. Inline-кнопки, ReplyKeyboard или оба?\n"
        "4. Платежи через Telegram Payments / ЮКасса?\n"
        "5. Деплой: systemd, Docker, Railway, Heroku?"
    ),
    phases=(
        "1. Структура проекта + FSM-состояния (пауза)\n"
        "2. Обработчики команд и callback\n"
        "3. БД-слой (если нужен)\n"
        "4. Платежи (если нужны)\n"
        "5. Деплой + мониторинг"
    ),
    verification="Запустить бота → пройти все основные сценарии, проверить FSM-переходы",
    upsell=["Панель администратора", "Рассылки", "Аналитика пользователей"],
    spec_hint="Зафиксируй: команды, сценарии FSM, БД, нужны ли платежи.",
))
