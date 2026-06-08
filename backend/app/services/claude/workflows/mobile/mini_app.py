from .._types import WorkflowDef, register

register(WorkflowDef(
    id="telegram_mini_app",
    task_type="new_site_mobile",
    label="Telegram Mini App (TMA)",
    keywords=["telegram mini app", "tma", "telegram webapp", "mini app"],
    credits_min=2000,
    credits_max=3500,
    key_pause="после инициализации WebApp SDK и первого экрана — подтверди UX",
    questionnaire=(
        "1. Функционал (магазин, квиз, бронирование, игра)?\n"
        "2. Стек frontend: React, Vue, Vanilla JS?\n"
        "3. Backend: нужен или встраиваемся в существующий бот?\n"
        "4. Telegram Payments внутри TMA?\n"
        "5. CloudStorage или свой бэкенд для данных?"
    ),
    phases=(
        "1. Telegram WebApp SDK + init (пауза)\n"
        "2. UI-экраны\n"
        "3. Backend API\n"
        "4. Платежи (если нужны)\n"
        "5. Деплой + привязка к боту"
    ),
    verification="Открыть TMA через бота → все экраны работают; haptic feedback; payments (если есть)",
    upsell=["Аналитика TMA (Yandex Metrika)", "Шаринг через bot link", "Notifications"],
    spec_hint="Зафиксируй: функционал, стек, нужен ли бэкенд, нужны ли платежи.",
))
