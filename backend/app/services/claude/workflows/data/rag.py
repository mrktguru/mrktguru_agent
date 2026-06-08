from .._types import WorkflowDef, register

register(WorkflowDef(
    id="rag_vector_db",
    task_type="ai_assistant",
    label="RAG / векторная БД",
    keywords=["rag", "векторная бд", "pgvector", "chromadb", "weaviate", "retrieval augmented"],
    credits_min=2000,
    credits_max=3000,
    key_pause="после индексации первых документов — оцени качество retrieval",
    questionnaire=(
        "1. Источник знаний (документы PDF, веб-сайт, Confluence, Notion, БД)?\n"
        "2. Векторное хранилище: pgvector, ChromaDB, Weaviate, Pinecone?\n"
        "3. Embedding-модель: text-embedding-3, E5, bge-m3?\n"
        "4. LLM для генерации ответов?\n"
        "5. Интерфейс: чат на сайте, Telegram-бот, API?"
    ),
    phases=(
        "1. Загрузка + чанкинг документов (пауза)\n"
        "2. Embedding + индексация\n"
        "3. Retrieval + re-ranking\n"
        "4. LLM generation + prompt\n"
        "5. Интерфейс + оценка качества"
    ),
    verification="Задать вопрос по документам → ответ релевантен, источник указан",
    upsell=["Hybrid search (BM25 + vector)", "Фидбэк и дообучение", "Аналитика вопросов"],
    spec_hint="Зафиксируй: источник знаний, векторное хранилище, LLM, интерфейс.",
))
