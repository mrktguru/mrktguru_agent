from .._types import WorkflowDef, register

register(WorkflowDef(
    id="webhook_handler",
    task_type="module",
    label="Webhook-обработчик",
    keywords=["webhook", "вебхук", "webhook handler", "событие от сервиса"],
    credits_min=500,
    credits_max=1000,
    key_pause="после схемы событий — подтверди список типов и логику обработки",
    questionnaire=(
        "1. Какой сервис шлёт события (GitHub, Stripe, Telegram, другой)?\n"
        "2. Список типов событий и что делать при каждом?\n"
        "3. Нужна верификация подписи (HMAC, secret)?\n"
        "4. Асинхронная обработка (очередь) или синхронная?\n"
        "5. Куда логировать / хранить события?"
    ),
    phases=(
        "1. Endpoint + верификация подписи (пауза)\n"
        "2. Парсинг payload + роутинг по типу\n"
        "3. Обработчики событий\n"
        "4. Логирование + retry-логика"
    ),
    verification="Отправить тестовый webhook → событие обработано, данные сохранены/переданы",
    upsell=["Дашборд событий", "Dead-letter queue", "Retry с exponential backoff"],
    spec_hint="Зафиксируй: сервис-источник, список событий, нужна ли HMAC-верификация.",
))
