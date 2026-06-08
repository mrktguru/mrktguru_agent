from .._types import WorkflowDef, register

register(WorkflowDef(
    id="wordpress",
    task_type="new_site",
    label="WordPress сайт / тема",
    keywords=["wordpress", "wp тема", "wordpress плагин", "elementor", "woocommerce"],
    credits_min=2000,
    credits_max=3000,
    key_pause="после структуры темы/плагина — подтверди хук-архитектуру",
    questionnaire=(
        "1. Кастомная тема или дочерняя от существующей?\n"
        "2. Нужны ли кастомные типы записей (CPT)?\n"
        "3. Page builder: Elementor, Gutenberg блоки, нет?\n"
        "4. WooCommerce нужен?\n"
        "5. Хостинг: shared / VPS / WP Engine?"
    ),
    phases=(
        "1. Структура темы: functions.php, template hierarchy (пауза)\n"
        "2. Кастомные хуки, CPT, мета-поля\n"
        "3. Frontend шаблоны\n"
        "4. Плагины + оптимизация скорости\n"
        "5. Деплой + бэкап"
    ),
    verification="WP Admin → страницы открываются, CPT работают, WooCommerce checkout (если нужен)",
    upsell=["SEO-плагин Yoast", "Кэширование WP Rocket", "Многоязычность WPML"],
    spec_hint="Зафиксируй: тема или плагин, CPT, нужен ли WooCommerce.",
))
