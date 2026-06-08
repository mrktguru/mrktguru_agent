from .._types import WorkflowDef, register

register(WorkflowDef(
    id="vps_setup",
    task_type="devops",
    label="VPS с нуля (nginx / SSL / деплой)",
    keywords=["vps", "сервер с нуля", "nginx ssl", "настройка сервера", "ubuntu server"],
    credits_min=1200,
    credits_max=2000,
    key_pause="после установки nginx и SSL-сертификата — проверь HTTPS",
    questionnaire=(
        "1. ОС: Ubuntu 22.04, Debian, другое?\n"
        "2. Что деплоить (Python/Node/PHP/Docker)?\n"
        "3. Домен уже есть, DNS настроен?\n"
        "4. Firewall (ufw), fail2ban нужны?\n"
        "5. Нужен ли swap, ограничения памяти для процессов?"
    ),
    phases=(
        "1. Базовая настройка: пользователь, SSH, ufw (пауза)\n"
        "2. nginx + certbot SSL\n"
        "3. Окружение приложения (Python/Node/Docker)\n"
        "4. systemd-сервис + автостарт\n"
        "5. Мониторинг + fail2ban"
    ),
    verification="HTTPS работает; сервис стартует при reboot; fail2ban активен",
    upsell=["CI/CD деплой", "Мониторинг Grafana", "Бэкап базы данных"],
    spec_hint="Зафиксируй: ОС, стек приложения, домен, нужен ли firewall.",
))
