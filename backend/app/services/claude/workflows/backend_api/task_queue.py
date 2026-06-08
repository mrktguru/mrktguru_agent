from .._types import WorkflowDef, register

register(WorkflowDef(
    id="task_queue",
    task_type="module",
    label="Очередь задач / фоновые задачи",
    keywords=["celery", "rq", "фоновые задачи", "task queue", "background tasks", "dramatiq"],
    credits_min=700,
    credits_max=1500,
    key_pause="после схемы задач и воркеров — подтверди список task-функций",
    questionnaire=(
        "1. Библиотека: Celery, RQ, Dramatiq, ARQ (async)?\n"
        "2. Брокер: Redis, RabbitMQ?\n"
        "3. Список фоновых задач (что делают, как запускаются)?\n"
        "4. Нужны ли периодические задачи (Celery Beat / cron)?\n"
        "5. Нужен ли Flower / мониторинг?"
    ),
    phases=(
        "1. Настройка брокера + worker (пауза)\n"
        "2. Task-функции\n"
        "3. Retry-политика + error handling\n"
        "4. Beat (периодические) если нужны\n"
        "5. Мониторинг + логирование"
    ),
    verification="Поставить задачу в очередь → worker выполнил, результат/логи в порядке",
    upsell=["Flower dashboard", "Результаты в БД", "Приоритезация очередей"],
    spec_hint="Зафиксируй: библиотека, брокер, список задач.",
))
