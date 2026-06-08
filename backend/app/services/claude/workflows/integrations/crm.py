from .._types import WorkflowDef, register

register(WorkflowDef(
    id="crm_integration",
    task_type="integration",
    label="CRM-интеграция (amoCRM / Битрикс / HubSpot)",
    keywords=["amocrm", "битрикс", "hubspot", "crm интеграция", "b24", "salesforce"],
    credits_min=1000,
    credits_max=1500,
    key_pause="после OAuth-авторизации и получения access_token — проверь доступ к API",
    questionnaire=(
        "1. CRM-система (amoCRM, Битрикс24, HubSpot, другая)?\n"
        "2. Что синхронизировать (лиды, сделки, контакты, задачи)?\n"
        "3. Направление: сайт→CRM, CRM→сайт, двустороннее?\n"
        "4. Триггер: форма сайта, webhook, расписание?\n"
        "5. Нужно ли создавать задачи/уведомления в CRM?"
    ),
    phases=(
        "1. OAuth / API-ключи + тест доступа (пауза)\n"
        "2. Маппинг полей сайт↔CRM\n"
        "3. Обработчики событий\n"
        "4. Webhook / polling\n"
        "5. Логирование + алерты"
    ),
    verification="Заполнить форму → лид появился в CRM с корректными полями",
    upsell=["Двусторонняя синхронизация", "Автоворонка", "CRM-виджет на сайте"],
    spec_hint="Зафиксируй: CRM, что синхронизировать, триггер, маппинг полей.",
))
