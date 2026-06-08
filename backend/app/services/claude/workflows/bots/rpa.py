from .._types import WorkflowDef, register

register(WorkflowDef(
    id="rpa",
    task_type="new_parser",
    label="RPA / GUI-автоматизация",
    keywords=["rpa", "pyautogui", "gui автоматизация", "selenium desktop", "pywinauto"],
    credits_min=1500,
    credits_max=2500,
    key_pause="после сценария шагов UI — подтверди метод локаторов (координаты / image matching)",
    questionnaire=(
        "1. Приложение: браузер, desktop (Win/Mac), или смешанный?\n"
        "2. Инструмент: PyAutoGUI, Playwright, Selenium, pywinauto?\n"
        "3. Сценарий по шагам (что кликать, куда вводить)?\n"
        "4. Частота запуска и расписание?\n"
        "5. Нужна ли обработка ошибок / captcha?"
    ),
    phases=(
        "1. Пошаговый сценарий + выбор инструмента (пауза)\n"
        "2. Скрипт автоматизации\n"
        "3. Логирование + error handling\n"
        "4. Планировщик (cron/Task Scheduler)"
    ),
    verification="Запустить скрипт → все шаги выполнены, результат в логах",
    upsell=["Headless режим", "Captcha-solver интеграция", "Dashboard с результатами"],
    spec_hint="Зафиксируй: приложение, инструмент, пошаговый сценарий.",
))
