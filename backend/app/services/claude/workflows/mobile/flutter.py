from .._types import WorkflowDef, register

register(WorkflowDef(
    id="flutter_app",
    task_type="new_site_mobile",
    label="Flutter приложение",
    keywords=["flutter", "dart", "flutter app"],
    credits_min=3000,
    credits_max=5000,
    key_pause="после виджетного дерева и навигации — подтверди основные экраны",
    questionnaire=(
        "1. Целевые платформы: iOS, Android, или Web тоже?\n"
        "2. State management: Bloc, Riverpod, GetX, Provider?\n"
        "3. Backend: REST API, Firebase, Supabase?\n"
        "4. Нативные фичи (камера, геолокация, биометрия)?\n"
        "5. Push-уведомления: Firebase FCM?"
    ),
    phases=(
        "1. Навигация (GoRouter/Navigator 2) + базовые экраны (пауза)\n"
        "2. State management + модели\n"
        "3. API/Firebase-слой\n"
        "4. UI-виджеты + темизация\n"
        "5. Нативные фичи + деплой"
    ),
    verification="Запустить на Android/iOS симуляторе → основные флоу без ошибок",
    upsell=["Публикация в Store", "Push-уведомления FCM", "Crashlytics"],
    spec_hint="Зафиксируй: платформы, state management, backend, нативные фичи.",
))
