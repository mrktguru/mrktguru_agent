from .._types import WorkflowDef, register

register(WorkflowDef(
    id="cdn_optimization",
    task_type="devops",
    label="CDN / ускорение сайта",
    keywords=["cdn", "cloudflare", "ускорить сайт", "оптимизация производительности", "pagespeed"],
    credits_min=600,
    credits_max=1000,
    key_pause="после подключения CDN — замерь PageSpeed до/после",
    questionnaire=(
        "1. CDN-провайдер: Cloudflare, AWS CloudFront, Fastly, BunnyCDN?\n"
        "2. Текущий PageSpeed score (если известен)?\n"
        "3. Что оптимизировать (статика, изображения, кэш HTML, TTFB)?\n"
        "4. Нужен ли edge caching для API-ответов?\n"
        "5. WAF / DDoS-защита нужна?"
    ),
    phases=(
        "1. Подключение CDN + DNS (пауза)\n"
        "2. Cache rules для статики\n"
        "3. Оптимизация изображений\n"
        "4. Минификация JS/CSS\n"
        "5. Замер PageSpeed + тюнинг"
    ),
    verification="PageSpeed 90+ mobile; Time to First Byte < 200ms; статика из CDN",
    upsell=["WAF правила", "Bot protection", "Image resizing на лету"],
    spec_hint="Зафиксируй: CDN-провайдер, текущий score, что оптимизировать.",
))
