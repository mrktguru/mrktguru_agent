from .._types import WorkflowDef, register

register(WorkflowDef(
    id="n8n_workflow",
    task_type="new_bot",
    label="n8n / Make / Zapier автоматизация",
    keywords=["n8n", "make", "zapier", "no-code автоматизация", "автоматизация процессов"],
    credits_min=600,
    credits_max=1200,
    key_pause="после схемы триггер→действия — подтверди нодовый граф",
    questionnaire=(
        "1. Платформа: n8n (self-hosted), Make.com, Zapier?\n"
        "2. Триггер (webhook, расписание, событие в системе)?\n"
        "3. Источники и назначения данных?\n"
        "4. Нужна ли обработка ошибок и retry?\n"
        "5. Self-hosted n8n — нужна установка на VPS?"
    ),
    phases=(
        "1. Схема: триггер → трансформации → действия (пауза)\n"
        "2. Настройка нодов + credentials\n"
        "3. Тестирование каждого шага\n"
        "4. Error handling + мониторинг"
    ),
    verification="Активировать workflow → прогнать тестовый сценарий от начала до конца",
    upsell=["n8n на VPS + SSL", "Monitoring через Slack", "Версионирование workflows"],
    spec_hint="Зафиксируй: платформа, триггер, источники/цели данных.",
))
