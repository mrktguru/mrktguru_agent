from .._types import WorkflowDef, register

register(WorkflowDef(
    id="ai_agent",
    task_type="ai_assistant",
    label="AI-агент (LangGraph / AutoGPT)",
    keywords=["ai агент", "langgraph", "autogpt", "autonomous agent", "tool-use agent"],
    credits_min=2500,
    credits_max=4000,
    key_pause="после определения инструментов агента — тест tool-use loop",
    questionnaire=(
        "1. Задача агента (исследование, автоматизация, кодинг, другое)?\n"
        "2. Фреймворк: LangGraph, LangChain, AutoGen, pure code?\n"
        "3. Список инструментов (web search, code exec, файловая система, API)?\n"
        "4. LLM: GPT-4o, Claude Opus, локальная?\n"
        "5. Human-in-the-loop checkpoint нужен?"
    ),
    phases=(
        "1. Граф состояний + инструменты (пауза)\n"
        "2. Agent loop + memory\n"
        "3. Tool implementations\n"
        "4. Human checkpoint\n"
        "5. Мониторинг + ограничения"
    ),
    verification="Запустить тест-задачу → агент использует инструменты, достигает цели",
    upsell=["Multi-agent система", "Long-term memory (Mem0)", "Аудит действий"],
    spec_hint="Зафиксируй: задача, фреймворк, список инструментов, нужен ли checkpoint.",
))
