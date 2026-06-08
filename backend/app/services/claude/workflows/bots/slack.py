from .._types import WorkflowDef, register

register(WorkflowDef(
    id="slack_bot",
    task_type="new_bot",
    label="Slack-бот",
    keywords=["slack", "slack bot", "slack app"],
    credits_min=1200,
    credits_max=2000,
    key_pause="после OAuth + Bolt-приложения — подтверди события и slash-команды",
    questionnaire=(
        "1. Slash-команды, events, shortcuts?\n"
        "2. Функционал: уведомления, опросы, CI/CD статусы, модерация?\n"
        "3. OAuth для установки в workspace или только dev-токен?\n"
        "4. Нужна ли БД?\n"
        "5. Деплой: AWS Lambda (Socket Mode), VPS, Heroku?"
    ),
    phases=(
        "1. Bolt app + OAuth + manifest (пауза)\n"
        "2. Обработчики команд и событий\n"
        "3. Block Kit UI\n"
        "4. Деплой"
    ),
    verification="Установить в тестовый workspace → slash-команды и события работают",
    upsell=["App Directory публикация", "Workflow Builder интеграция", "Analytics"],
    spec_hint="Зафиксируй: тип событий, slash-команды, нужен ли OAuth.",
))
