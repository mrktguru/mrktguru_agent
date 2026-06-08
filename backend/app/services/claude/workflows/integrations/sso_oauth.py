from .._types import WorkflowDef, register

register(WorkflowDef(
    id="sso_oauth",
    task_type="integration",
    label="SSO / OAuth (Google, GitHub, VK, Яндекс)",
    keywords=["sso", "oauth", "google auth", "github auth", "социальный логин", "vk auth", "yandex auth"],
    credits_min=600,
    credits_max=1000,
    key_pause="после регистрации OAuth-приложения — верифицируй redirect_uri и scopes",
    questionnaire=(
        "1. Провайдеры (Google, GitHub, VK, Яндекс, Microsoft, Apple)?\n"
        "2. Стек: NextAuth, Passport.js, Authlib, django-allauth?\n"
        "3. Связка с локальными аккаунтами или только OAuth?\n"
        "4. Нужен ли доступ к данным профиля (фото, email)?\n"
        "5. Обработка ситуации: один email у двух провайдеров?"
    ),
    phases=(
        "1. Регистрация OAuth-приложений + ключи (пауза)\n"
        "2. Настройка библиотеки авторизации\n"
        "3. Callback-роуты и маппинг профиля\n"
        "4. Связка с локальными аккаунтами\n"
        "5. Тест всех провайдеров"
    ),
    verification="Войти через каждый провайдер → профиль создан/связан корректно",
    upsell=["2FA поверх OAuth", "SAML для Enterprise", "Audit log входов"],
    spec_hint="Зафиксируй: провайдеры, библиотека, обработка дублей email.",
))
