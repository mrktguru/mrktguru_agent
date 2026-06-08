from .._types import WorkflowDef, register

register(WorkflowDef(
    id="email_template",
    task_type="module",
    label="Email-шаблон / транзакционное письмо",
    keywords=["email шаблон", "транзакционное письмо", "html письмо", "email template"],
    credits_min=400,
    credits_max=800,
    key_pause="после HTML-каркаса — проверь рендеринг в Litmus/Can I email",
    questionnaire=(
        "1. Тип письма (приветствие, заказ, восстановление пароля, рассылка)?\n"
        "2. Сервис отправки (SendGrid, Mailchimp, PostmarkApp, SMTP)?\n"
        "3. Переменные-подстановки (имя, сумма, ссылка)?\n"
        "4. Дизайн: по макету или базовый корпоративный стиль?"
    ),
    phases=(
        "1. HTML-скелет (table-based, inline CSS) (пауза)\n"
        "2. Адаптив для мобильных\n"
        "3. Тёмная тема (prefers-color-scheme)\n"
        "4. Интеграция в сервис отправки + тест"
    ),
    verification="Отправить тестовое письмо → проверить в Gmail/Outlook/Apple Mail",
    upsell=["Серия onboarding-писем", "A/B тест тем", "Аналитика открытий"],
    spec_hint="Зафиксируй: тип письма, сервис, список переменных.",
))
