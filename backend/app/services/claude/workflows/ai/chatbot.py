from .._types import WorkflowDef, register

register(WorkflowDef(
    id="ai_chatbot",
    task_type="ai_assistant",
    label="AI-чатбот (виджет / сайт)",
    keywords=["ai чатбот", "виджет чат", "ai поддержка", "чат с ai", "chatbot"],
    credits_min=2000,
    credits_max=3000,
    key_pause="после system prompt и первых тест-диалогов — оцени качество ответов",
    questionnaire=(
        "1. Назначение чатбота (поддержка, продажи, FAQ, onboarding)?\n"
        "2. База знаний: документы, FAQ, CRM?\n"
        "3. LLM: GPT-4o, Claude, Gemini, или локальная модель?\n"
        "4. Интерфейс: виджет на сайте, Telegram, WhatsApp?\n"
        "5. Human handoff нужен?"
    ),
    phases=(
        "1. System prompt + база знаний (пауза)\n"
        "2. LLM-интеграция + история диалога\n"
        "3. UI-виджет\n"
        "4. Human handoff\n"
        "5. Аналитика вопросов"
    ),
    verification="Задать типичные вопросы → ответы корректны; human handoff работает",
    upsell=["RAG по документам", "Аналитика диалогов", "Мультиязычность"],
    spec_hint="Зафиксируй: назначение, база знаний, LLM, интерфейс.",
))
