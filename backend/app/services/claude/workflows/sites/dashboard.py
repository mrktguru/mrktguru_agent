from .._types import WorkflowDef, register

register(WorkflowDef(
    id="dashboard",
    task_type="new_site",
    label="Аналитический дашборд",
    keywords=["дашборд", "dashboard", "аналитика csv", "панель управления", "графики"],
    credits_min=2000,
    credits_max=3000,
    key_pause="после схемы данных и набора виджетов — подтверди список метрик",
    questionnaire=(
        "1. Источник данных (CSV/Excel, PostgreSQL, API, Google Sheets)?\n"
        "2. Стек: React + Recharts/Chart.js, Streamlit, Metabase, Grafana?\n"
        "3. Список виджетов/метрик (KPI-карточки, линейные, pie, таблицы)?\n"
        "4. Нужна ли авторизация и разграничение доступа?\n"
        "5. Как часто обновляются данные (реалтайм, раз в час, ручной upload)?"
    ),
    phases=(
        "1. Источник данных + схема (пауза)\n"
        "2. API/слой данных\n"
        "3. Компоненты виджетов\n"
        "4. Layout дашборда + фильтры\n"
        "5. Авторизация + деплой"
    ),
    verification="Загрузить тестовые данные → все виджеты показывают корректные значения",
    upsell=["Экспорт в PDF/Excel", "Алерты по порогам", "Мобильная версия"],
    spec_hint="Зафиксируй: источник данных, список виджетов, стек.",
))
