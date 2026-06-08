from .._types import WorkflowDef, register

register(WorkflowDef(
    id="bi_reports",
    task_type="new_site",
    label="BI-система / аналитические отчёты",
    keywords=["bi", "metabase", "superset", "tableau", "аналитика данных", "business intelligence"],
    credits_min=1500,
    credits_max=2500,
    key_pause="после подключения к БД и первого дашборда — подтверди список метрик",
    questionnaire=(
        "1. BI-инструмент: Metabase, Apache Superset, Grafana, другой?\n"
        "2. Источник данных (PostgreSQL, ClickHouse, BigQuery)?\n"
        "3. Список нужных отчётов/дашбордов?\n"
        "4. Разграничение доступа по ролям?\n"
        "5. Нужна ли выгрузка в Excel/PDF?"
    ),
    phases=(
        "1. Установка BI + подключение источника (пауза)\n"
        "2. Базовые метрики и вопросы\n"
        "3. Дашборды\n"
        "4. Роли и доступы\n"
        "5. Алерты + расписание отчётов"
    ),
    verification="Открыть дашборд → данные актуальны; роли ограничивают доступ корректно",
    upsell=["Автоматическая рассылка отчётов", "Embedded analytics", "ML-прогнозы"],
    spec_hint="Зафиксируй: BI-инструмент, источник, список дашбордов.",
))
