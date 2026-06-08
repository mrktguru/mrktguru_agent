from .._types import WorkflowDef, register

register(WorkflowDef(
    id="docker_setup",
    task_type="devops",
    label="Docker / Docker Compose",
    keywords=["docker", "docker-compose", "dockerfile", "контейнеризация", "docker compose"],
    credits_min=700,
    credits_max=1200,
    key_pause="после Dockerfile — проверь размер образа и запуск контейнера",
    questionnaire=(
        "1. Что контейнеризировать (web, worker, БД, nginx, все вместе)?\n"
        "2. Docker Compose для local dev или prod тоже?\n"
        "3. Отдельный registry (Docker Hub, GitHub CR, Yandex CR)?\n"
        "4. Volumes для persistent data?\n"
        "5. Нужен ли multi-stage build для уменьшения размера?"
    ),
    phases=(
        "1. Dockerfile + .dockerignore (пауза)\n"
        "2. docker-compose.yml + сети\n"
        "3. Volumes + env-файлы\n"
        "4. Health checks\n"
        "5. Оптимизация размера образа"
    ),
    verification="docker compose up → все сервисы healthy; приложение доступно",
    upsell=["Kubernetes манифесты", "Helm chart", "Container scanning (Trivy)"],
    spec_hint="Зафиксируй: список сервисов, нужен ли registry, persistent volumes.",
))
