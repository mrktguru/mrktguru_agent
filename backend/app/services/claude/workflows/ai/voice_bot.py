from .._types import WorkflowDef, register

register(WorkflowDef(
    id="voice_bot",
    task_type="ai_assistant",
    label="Голосовой бот (TTS/STT)",
    keywords=["голосовой бот", "tts stt", "whisper", "voice assistant", "speech recognition"],
    credits_min=2500,
    credits_max=4000,
    key_pause="после первого полного цикла STT→LLM→TTS — оцени латентность",
    questionnaire=(
        "1. Платформа: телефония (Asterisk/Twilio Voice), Telegram Voice, web?\n"
        "2. STT: Whisper, Google STT, Yandex SpeechKit?\n"
        "3. TTS: ElevenLabs, Yandex TTS, Google TTS?\n"
        "4. Сценарий диалога (фиксированный IVR или свободный LLM)?\n"
        "5. Язык / акцент требования?"
    ),
    phases=(
        "1. STT + TTS тест-конфигурация (пауза)\n"
        "2. Диалоговая логика / LLM\n"
        "3. Интеграция с платформой\n"
        "4. Оптимизация латентности\n"
        "5. Аналитика звонков"
    ),
    verification="Полный голосовой диалог → STT корректно, TTS натуральное; задержка < 2с",
    upsell=["Распознавание эмоций", "CRM-запись звонков", "Многоязычный режим"],
    spec_hint="Зафиксируй: платформа, STT, TTS, тип диалога (IVR или LLM).",
))
