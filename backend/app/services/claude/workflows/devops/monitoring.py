from .._types import WorkflowDef, register

register(WorkflowDef(
    id="monitoring_setup",
    task_type="devops",
    label="Мониторинг (Grafana / Prometheus / Sentry)",
    keywords=["мониторинг", "grafana", "prometheus", "sentry", "alertmanager", "uptime"],
    credits_min=700,
    credits_max=1500,
    key_pause="после первых метрик в Prometheus/Grafana — подтверди список дашбордов",
    questionnaire=(
        "1. Стек: Prometheus + Grafana, Sentry, Datadog, uptimerobot?\n"
        "2. Что мониторить (uptime, CPU/RAM, ошибки, бизнес-метрики)?\n"
        "3. Алерты куда (Telegram, Slack, email, PagerDuty)?\n"
        "4. Логи: ELK, Loki + Grafana, или cloud-логи?\n"
        "5. Self-hosted или cloud?"
    ),
    phases=(
        "1. Экспортёры + Prometheus scrape (пауза)\n"
        "2. Grafana дашборды\n"
        "3. Alertmanager + каналы уведомлений\n"
        "4. Лог-агрегация\n"
        "5. Runbook для алертов"
    ),
    verification="Дашборд показывает метрики; тестовый алерт получен в нужный канал",
    upsell=["Distributed tracing (Jaeger)", "SLO/SLA tracking", "Synthetic monitoring"],
    spec_hint="Зафиксируй: стек, что мониторить, куда алерты.",
))
