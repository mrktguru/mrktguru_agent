from .._types import WorkflowDef, register

register(WorkflowDef(
    id="cicd_pipeline",
    task_type="devops",
    label="CI/CD пайплайн",
    keywords=["ci/cd", "github actions", "gitlab ci", "jenkins", "pipeline", "автодеплой"],
    credits_min=700,
    credits_max=1500,
    key_pause="после первого успешного прогона пайплайна — подтверди стадии",
    questionnaire=(
        "1. Платформа: GitHub Actions, GitLab CI, Jenkins, другая?\n"
        "2. Стадии: lint → test → build → deploy → notify?\n"
        "3. Куда деплоить (VPS, Kubernetes, AWS, Vercel)?\n"
        "4. Нужны ли review apps для PR?\n"
        "5. Секреты: GitHub Secrets, Vault, переменные окружения?"
    ),
    phases=(
        "1. Базовый workflow: lint + test (пауза)\n"
        "2. Build (Docker, npm build и т.д.)\n"
        "3. Deploy стадия\n"
        "4. Уведомления (Slack, Telegram)\n"
        "5. Кэш + оптимизация скорости"
    ),
    verification="Push → пайплайн прошёл; деплой применён на целевой среде",
    upsell=["Staging окружение", "Canary deploy", "Rollback автоматический"],
    spec_hint="Зафиксируй: платформа, стадии, цель деплоя.",
))
