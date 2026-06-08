from .._types import WorkflowDef, register

register(WorkflowDef(
    id="ml_pipeline",
    task_type="new_parser",
    label="ML-пайплайн",
    keywords=["ml", "pytorch", "tensorflow", "sklearn", "машинное обучение", "модель ml"],
    credits_min=2500,
    credits_max=4000,
    key_pause="после EDA и baseline-метрик — подтверди архитектуру модели",
    questionnaire=(
        "1. Задача: классификация, регрессия, кластеризация, NLP, CV?\n"
        "2. Данные: есть набор или нужен сбор?\n"
        "3. Фреймворк: scikit-learn, PyTorch, TensorFlow?\n"
        "4. Инференс: API-сервис, batch, edge-устройство?\n"
        "5. MLOps: MLflow, DVC, или просто скрипты?"
    ),
    phases=(
        "1. EDA + baseline (пауза)\n"
        "2. Предобработка + feature engineering\n"
        "3. Обучение + валидация\n"
        "4. Инференс-сервис\n"
        "5. Мониторинг качества"
    ),
    verification="Тестовый инференс → предсказание получено; метрики не хуже baseline",
    upsell=["A/B тест моделей", "Дообучение на новых данных", "Explainability (SHAP)"],
    spec_hint="Зафиксируй: задача ML, фреймворк, формат данных, нужен ли инференс-API.",
))
