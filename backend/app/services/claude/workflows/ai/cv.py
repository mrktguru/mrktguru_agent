from .._types import WorkflowDef, register

register(WorkflowDef(
    id="computer_vision",
    task_type="ai_assistant",
    label="Computer Vision (YOLO / детекция)",
    keywords=["computer vision", "yolo", "детекция", "object detection", "opencv ml"],
    credits_min=2000,
    credits_max=3500,
    key_pause="после первой inference на тест-изображениях — оцени точность",
    questionnaire=(
        "1. Задача CV: детекция, классификация, сегментация, OCR, pose estimation?\n"
        "2. Модель: YOLOv8/11, EfficientDet, кастомная CNN?\n"
        "3. Данные: готовый датасет или нужна разметка?\n"
        "4. Инференс: реалтайм (webcam/видеопоток) или пакетный?\n"
        "5. Деплой: API-сервис, edge-устройство, облако?"
    ),
    phases=(
        "1. Датасет + baseline inference (пауза)\n"
        "2. Fine-tuning / обучение\n"
        "3. Инференс-сервис\n"
        "4. Постобработка результатов\n"
        "5. Деплой + мониторинг качества"
    ),
    verification="Тест-изображения → детекция корректна; FPS приемлем для реалтайм",
    upsell=["Видео-аналитика", "Аннотация данных", "Edge-деплой (ONNX/TensorRT)"],
    spec_hint="Зафиксируй: задача CV, модель, датасет, режим инференса.",
))
