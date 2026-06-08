from .._types import WorkflowDef, register

register(WorkflowDef(
    id="email_marketing",
    task_type="integration",
    label="Email-маркетинг (SendGrid / Mailchimp / Unisender)",
    keywords=["sendgrid", "mailchimp", "unisender", "email рассылка", "transactional email"],
    credits_min=700,
    credits_max=1200,
    key_pause="после верификации домена и тест-отправки — подтверди шаблоны",
    questionnaire=(
        "1. Сервис (SendGrid, Mailchimp, Unisender, Postmark, другой)?\n"
        "2. Тип писем: транзакционные, рассылки, или оба?\n"
        "3. Триггеры для транзакционных (регистрация, заказ, сброс пароля)?\n"
        "4. Нужна ли синхронизация контактов из БД?\n"
        "5. SPF/DKIM уже настроены?"
    ),
    phases=(
        "1. API-ключ + верификация домена + тест (пауза)\n"
        "2. Шаблоны писем\n"
        "3. Отправка из кода по триггерам\n"
        "4. Синхронизация контактов\n"
        "5. Мониторинг доставляемости"
    ),
    verification="Триггерное действие → письмо получено; SPF/DKIM pass",
    upsell=["Drip-кампания", "A/B тест тем", "Аналитика открытий/кликов"],
    spec_hint="Зафиксируй: сервис, тип писем, список триггеров.",
))
