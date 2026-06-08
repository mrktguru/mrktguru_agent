from .._types import WorkflowDef, register

register(WorkflowDef(
    id="pwa",
    task_type="feature",
    label="PWA / Service Worker / оффлайн",
    keywords=["pwa", "service worker", "оффлайн", "установить приложение", "web app manifest"],
    credits_min=800,
    credits_max=1500,
    key_pause="после manifest.json + базового SW — проверь установку в Chrome",
    questionnaire=(
        "1. Какие страницы/ресурсы кэшировать оффлайн?\n"
        "2. Стратегия кэша: cache-first, network-first, stale-while-revalidate?\n"
        "3. Push-уведомления нужны?\n"
        "4. Текущий стек (CRA, Vite, Next.js, plain HTML)?"
    ),
    phases=(
        "1. manifest.json + иконки + meta в head\n"
        "2. Service Worker: precache + runtime cache (пауза)\n"
        "3. Оффлайн-страница\n"
        "4. Тест Lighthouse PWA score"
    ),
    verification="Lighthouse PWA: все зелёные; отключить сеть → оффлайн-страница работает",
    upsell=["Push-уведомления", "Background sync", "App-like анимации"],
    spec_hint="Зафиксируй: стратегия кэша, список URL для precache, нужны ли push.",
))
