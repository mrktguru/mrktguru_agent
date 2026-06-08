from .._types import WorkflowDef, register

register(WorkflowDef(
    id="image_processing",
    task_type="module",
    label="Обработка изображений",
    keywords=["обработка изображений", "pillow", "opencv", "imagemagick", "ресайз фото"],
    credits_min=700,
    credits_max=1200,
    key_pause="после определения pipeline операций — подтверди форматы входа/выхода",
    questionnaire=(
        "1. Операции: ресайз, кроп, watermark, конвертация, фильтры?\n"
        "2. Входной формат и ожидаемый выход?\n"
        "3. Обработка разовая, пакетная или в реалтайм (при загрузке)?\n"
        "4. Библиотека: Pillow, OpenCV, ImageMagick, Sharp (Node)?\n"
        "5. Нужен ли API-сервис или CLI-скрипт?"
    ),
    phases=(
        "1. Pipeline операций + тест на сэмплах (пауза)\n"
        "2. Реализация обработчика\n"
        "3. Пакетная обработка / очередь\n"
        "4. Интеграция в загрузку файлов"
    ),
    verification="Обработать тестовый набор → выходные файлы соответствуют ожиданиям",
    upsell=["CDN с on-the-fly трансформацией", "ML-детекция объектов", "Face recognition"],
    spec_hint="Зафиксируй: список операций, формат вход/выход, реалтайм или пакет.",
))
