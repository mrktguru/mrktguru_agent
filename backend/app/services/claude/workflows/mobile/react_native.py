from .._types import WorkflowDef, register

register(WorkflowDef(
    id="react_native",
    task_type="new_site_mobile",
    label="React Native / Expo приложение",
    keywords=["react native", "expo", "rn", "mobile react"],
    credits_min=3000,
    credits_max=5000,
    key_pause="после навигационного стека и базовых экранов — подтверди UX-флоу",
    questionnaire=(
        "1. Expo (managed/bare) или чистый React Native (bare workflow)?\n"
        "2. Навигация: React Navigation (Stack, Tab, Drawer)?\n"
        "3. Состояние: Zustand, Redux Toolkit, Jotai?\n"
        "4. Backend: существующий API или нужно создать?\n"
        "5. Push-уведомления (Expo Notifications / Firebase FCM)?"
    ),
    phases=(
        "1. Навигация + базовые экраны (пауза)\n"
        "2. State management\n"
        "3. API-слой\n"
        "4. UI-компоненты + анимации\n"
        "5. Push-уведомления + деплой в Store"
    ),
    verification="Запустить на Android/iOS эмуляторе → все основные флоу работают",
    upsell=["Публикация в App Store/Play Market", "OTA-обновления EAS", "Аналитика"],
    spec_hint="Зафиксируй: Expo или bare, навигация, state, нужны ли push.",
))
