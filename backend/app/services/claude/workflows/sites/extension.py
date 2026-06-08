from .._types import WorkflowDef, register

register(WorkflowDef(
    id="extension",
    task_type="new_site",
    label="Chrome/Firefox расширение",
    keywords=["расширение", "chrome extension", "manifest v3", "browser extension", "firefox addon"],
    credits_min=1200,
    credits_max=2000,
    key_pause="после manifest.json и структуры popup/background — подтверди permissions",
    questionnaire=(
        "1. Что делает расширение (popup / content script / background)?\n"
        "2. Нужен ли доступ к текущей странице (content script)?\n"
        "3. Хранение данных: localStorage, chrome.storage или удалённый API?\n"
        "4. Нужна ли авторизация пользователя?"
    ),
    phases=(
        "1. manifest.json v3 + структура файлов (пауза)\n"
        "2. Popup UI (React или vanilla)\n"
        "3. Content script / background service worker\n"
        "4. Сборка (Vite/webpack) + инструкция по загрузке в Chrome"
    ),
    verification="Загрузить unpacked в chrome://extensions → popup открывается, функция работает",
    upsell=["Публикация в Chrome Web Store", "Синхронизация через chrome.storage.sync", "Firefox-порт"],
    spec_hint="Зафиксируй: тип (popup/content/background), необходимые permissions, хранилище.",
))
