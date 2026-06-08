from .._types import WorkflowDef, register

register(WorkflowDef(
    id="i18n",
    task_type="feature",
    label="Мультиязычность / i18n",
    keywords=["мультиязычный", "i18n", "локализация", "перевод сайта", "multilang"],
    credits_min=1000,
    credits_max=2000,
    key_pause="после настройки роутинга языков — подтверди структуру URL (prefix/subdomain)",
    questionnaire=(
        "1. Какие языки (список)?\n"
        "2. Стек: Next.js next-i18next, React i18next, Django, другое?\n"
        "3. URL-стратегия: /ru/, /en/ или subdomains?\n"
        "4. Переводы уже есть или нужно подготовить структуру?\n"
        "5. Нужен ли переключатель языка в UI?"
    ),
    phases=(
        "1. Настройка библиотеки i18n + роутинг языков (пауза)\n"
        "2. Экстракция строк в translation-файлы\n"
        "3. Компоненты: хук useTranslation / директива trans\n"
        "4. SEO: hreflang теги, sitemap по языкам"
    ),
    verification="Переключить язык → проверить URL, все строки переведены, hreflang в head",
    upsell=["Автоперевод через DeepL API", "RTL-поддержка", "Локализация дат/валют"],
    spec_hint="Зафиксируй: языки, стратегия URL, библиотека i18n.",
))
