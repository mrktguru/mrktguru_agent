from .._types import WorkflowDef, register

register(WorkflowDef(
    id="cron_service",
    task_type="module",
    label="Cron-сервис / планировщик",
    keywords=["cron", "apscheduler", "планировщик", "расписание задач", "scheduler"],
    credits_min=500,
    credits_max=1000,
    key_pause="после списка задач и расписания — подтверди cron-выражения",
    questionnaire=(
        "1. Инструмент: APScheduler, Celery Beat, node-cron, системный cron?\n"
        "2. Список задач с расписанием (cron-выражения или человеческое описание)?\n"
        "3. Нужна ли персистентность задач (restart-safe)?\n"
        "4. Уведомления при ошибке (email, Telegram, Slack)?\n"
        "5. Параллельные запуски допустимы или нужен distributed lock?"
    ),
    phases=(
        "1. Настройка планировщика + список задач (пауза)\n"
        "2. Реализация функций задач\n"
        "3. Error handling + уведомления\n"
        "4. Distributed lock (если нужен)\n"
        "5. Деплой + logrotate"
    ),
    verification="Запустить → ближайшая задача выполняется по расписанию; логи чистые",
    upsell=["Admin UI для управления задачами", "Distributed lock через Redis", "Алерты"],
    spec_hint="Зафиксируй: инструмент, список задач с расписанием, нужен ли lock.",
))
