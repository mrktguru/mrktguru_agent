from .._types import WorkflowDef, register

register(WorkflowDef(
    id="vk_bot",
    task_type="new_bot",
    label="VK-бот / сообщество",
    keywords=["vk", "вконтакте", "вк бот", "vk bot", "vk api"],
    credits_min=1000,
    credits_max=1800,
    key_pause="после настройки Callback API — подтверди список событий и команд",
    questionnaire=(
        "1. Longpoll или Callback API?\n"
        "2. Функционал: поддержка, продажи, автоответ, конкурсы?\n"
        "3. Клавиатура (кнопки) нужна?\n"
        "4. Интеграция с VK Pay или магазином?\n"
        "5. БД для хранения пользователей?"
    ),
    phases=(
        "1. Настройка сообщества + Callback/Longpoll (пауза)\n"
        "2. Обработчики событий и команд\n"
        "3. Клавиатура + карусели\n"
        "4. БД-слой + деплой"
    ),
    verification="Написать боту → ответ по сценарию, кнопки работают",
    upsell=["VK Реклама интеграция", "Рассылки через Senler", "Аналитика сообщества"],
    spec_hint="Зафиксируй: тип API, функционал, нужна ли клавиатура.",
))
