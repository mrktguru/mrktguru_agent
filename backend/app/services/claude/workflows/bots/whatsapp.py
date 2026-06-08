from .._types import WorkflowDef, register

register(WorkflowDef(
    id="whatsapp_bot",
    task_type="new_bot",
    label="WhatsApp-бот",
    keywords=["whatsapp", "вотсап", "whatsapp bot", "wa bot"],
    credits_min=1500,
    credits_max=2500,
    key_pause="после выбора API-провайдера — уточни сценарии сообщений",
    questionnaire=(
        "1. API: WhatsApp Business API (Meta), Twilio, или библиотека (whatsapp-web.js)?\n"
        "2. Основные сценарии: поддержка, уведомления, продажи?\n"
        "3. Нужна ли передача на оператора (human handoff)?\n"
        "4. CRM-интеграция?\n"
        "5. Объём сообщений в сутки?"
    ),
    phases=(
        "1. Настройка провайдера + webhook (пауза)\n"
        "2. Обработчик сообщений + сценарии\n"
        "3. Интеграция с CRM/БД\n"
        "4. Human handoff\n"
        "5. Деплой + мониторинг"
    ),
    verification="Отправить тестовое сообщение → бот отвечает по сценарию",
    upsell=["Шаблонные сообщения (approved)", "CRM-синхронизация", "Аналитика"],
    spec_hint="Зафиксируй: провайдер, сценарии, нужен ли human handoff.",
))
