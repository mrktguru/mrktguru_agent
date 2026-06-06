"""Command allowlist for ops/security tracks.

For high-risk intents (ops/security/maintenance/data_migration) the agent's
run_command tool is restricted to a vetted set of operations. Anything outside
the allowlist must go through request_user_input (human confirmation) rather than
being executed blind on production.
"""
from __future__ import annotations

import re

# Prefixes considered safe to run autonomously for ops tracks.
_OPS_ALLOWLIST = (
    "docker compose", "docker ps", "docker logs", "docker inspect",
    "nginx -t", "nginx -s reload", "nginx -T",
    "systemctl status", "systemctl restart", "systemctl reload",
    "systemctl enable", "systemctl disable", "systemctl start", "systemctl stop",
    "journalctl",
    "certbot", "ls", "cat", "grep", "tail", "head", "find", "df", "du",
    "curl", "ping", "dig", "nslookup", "openssl", "ss", "netstat",
    "wp ", "php ", "composer ", "npm run build", "npm ci", "npm install",
    # DevOps / bot agent additions
    "git ", "git clone", "git pull", "git status", "git log",
    "pip ", "pip3 ", "pip install", "pip3 install",
    "python ", "python3 ",
    "ufw ", "ufw status", "firewall-cmd",
    "apt ", "apt-get ", "yum ", "dnf ",
    "crontab", "crontab -l", "crontab -e",
    "tar ", "rsync ", "scp ",
    "mkdir ", "chmod ", "chown ",
    "ln -s", "ln -sf",
    "touch ", "cp ", "mv ",
    "which ", "whoami", "id ", "pwd",
    "ps aux", "ps -ef", "kill ", "pkill ",
    "free ", "uptime", "uname ",
    "wc ", "sort ", "uniq ", "awk ", "sed ",
    "echo ", "env ", "printenv",
    "node ", "npm ", "yarn ", "pnpm ",
    "uvicorn", "gunicorn",
)

# Never allowed, even for ops (destructive / irreversible without explicit human action).
_DENYLIST_RE = re.compile(
    r"\brm\s+-rf\s+/(?:\s|$)"
    r"|\brm\s+-rf\s+~"
    r"|\brm\s+-rf\s+/home"
    r"|\bmkfs|\bdd\s+if=|:\(\)\s*\{|>\s*/dev/sd"
    r"|\bdrop\s+database\b|\btruncate\b|\bgit\s+push\s+--force",
    re.IGNORECASE,
)


def is_destructive(cmd: str) -> bool:
    return bool(_DENYLIST_RE.search(cmd or ""))


def ops_command_allowed(cmd: str) -> bool:
    """True if cmd is safe to auto-run for an ops/security track."""
    c = (cmd or "").strip()
    if not c or is_destructive(c):
        return False
    # Allow if any command in a chain starts with an allowed prefix and none are destructive.
    parts = re.split(r"&&|\|\||;|\|", c)
    for p in parts:
        p = p.strip()
        if not p:
            continue
        if is_destructive(p):
            return False
        if not any(p.startswith(pref) for pref in _OPS_ALLOWLIST):
            return False
    return True
