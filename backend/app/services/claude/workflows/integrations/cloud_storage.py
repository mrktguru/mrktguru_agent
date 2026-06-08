from .._types import WorkflowDef, register

register(WorkflowDef(
    id="cloud_storage",
    task_type="integration",
    label="Облачное хранилище (S3 / Yandex Object Storage)",
    keywords=["s3", "yandex object storage", "bucket", "minio", "облачный файлы", "хранилище файлов"],
    credits_min=600,
    credits_max=1000,
    key_pause="после настройки bucket и тест-загрузки — верифицируй публичный доступ",
    questionnaire=(
        "1. Провайдер: AWS S3, Yandex Object Storage, MinIO, Cloudflare R2?\n"
        "2. Что хранить (аватары, документы, media, бэкапы)?\n"
        "3. Публичный доступ к файлам или presigned URLs?\n"
        "4. CDN перед bucket нужен?\n"
        "5. Нужна ли image-трансформация (ресайз при загрузке)?"
    ),
    phases=(
        "1. Bucket + IAM-политики + тест-загрузка (пауза)\n"
        "2. Клиент загрузки (прямая/presigned)\n"
        "3. Интеграция в формы/API\n"
        "4. CDN (если нужен)\n"
        "5. Lifecycle-политики (удаление старых файлов)"
    ),
    verification="Загрузить файл через UI → скачать по URL; lifecycle правила активны",
    upsell=["Image processing при загрузке", "CDN Cloudflare", "Аудит доступа"],
    spec_hint="Зафиксируй: провайдер, тип файлов, публичный/presigned, нужен ли CDN.",
))
