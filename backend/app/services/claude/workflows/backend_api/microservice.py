from .._types import WorkflowDef, register

register(WorkflowDef(
    id="microservice",
    task_type="module",
    label="Микросервис",
    keywords=["микросервис", "microservice", "сервис-компонент", "grpc сервис"],
    credits_min=800,
    credits_max=1500,
    key_pause="после интерфейса сервиса (API/gRPC/events) — подтверди контракт",
    questionnaire=(
        "1. Протокол: REST, gRPC, message broker (RabbitMQ/Kafka)?\n"
        "2. Ответственность сервиса (одна функция)?\n"
        "3. БД: отдельная или shared?\n"
        "4. Service discovery: Kubernetes, Consul, прямые URL?\n"
        "5. Нужна ли трассировка (OpenTelemetry)?"
    ),
    phases=(
        "1. Интерфейс + структура сервиса (пауза)\n"
        "2. Бизнес-логика\n"
        "3. БД-слой\n"
        "4. Docker + health checks\n"
        "5. Документация API"
    ),
    verification="Docker compose up → health check 200; запрос через API/gRPC возвращает данные",
    upsell=["Kubernetes HPA", "Distributed tracing", "Circuit breaker"],
    spec_hint="Зафиксируй: протокол, ответственность, нужна ли трассировка.",
))
