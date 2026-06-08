from .._types import WorkflowDef, register

register(WorkflowDef(
    id="etl_pipeline",
    task_type="new_parser",
    label="ETL-пайплайн",
    keywords=["etl", "airflow", "data pipeline", "dbt", "data engineering", "prefect"],
    credits_min=2000,
    credits_max=3000,
    key_pause="после схемы источников и целевой схемы данных — подтверди трансформации",
    questionnaire=(
        "1. Источники данных (PostgreSQL, S3, API, Kafka, файлы)?\n"
        "2. Целевое хранилище (DWH, PostgreSQL, BigQuery, ClickHouse)?\n"
        "3. Оркестратор: Apache Airflow, Prefect, dbt+cron?\n"
        "4. Расписание и объём данных?\n"
        "5. Нужна ли дедупликация и обработка пропусков?"
    ),
    phases=(
        "1. Схема источников → целевые таблицы (пауза)\n"
        "2. Extract: коннекторы к источникам\n"
        "3. Transform: очистка, нормализация, обогащение\n"
        "4. Load: запись в целевое хранилище\n"
        "5. DAG + мониторинг"
    ),
    verification="Запустить DAG → данные в целевом хранилище; lineage в логах",
    upsell=["Data quality тесты (Great Expectations)", "Alerting", "BI-дашборд"],
    spec_hint="Зафиксируй: источники, целевое хранилище, оркестратор, расписание.",
))
