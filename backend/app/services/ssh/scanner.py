"""SiteScanner — detects CMS, PHP version, web server, site root, and file structure."""
from __future__ import annotations

import re

from app.services.ssh.client import SSHClient


class SiteScanner:
    """Wraps SSHClient with site-level (not server-level) scanning logic."""

    def __init__(self, ssh: SSHClient) -> None:
        self._ssh = ssh

    def scan(self) -> dict:
        """Return a dict with cms, cms_version, php_version, web_server, server_os,
        site_root_path, file_structure, installed_plugins."""
        result: dict = {}

        result["server_os"] = self._get_os()
        result["php_version"] = self._get_php_version()
        result["web_server"] = self._get_web_server()
        result["site_root_path"] = self._get_site_root()
        cms, cms_version = self._detect_cms(result.get("site_root_path", ""))
        result["cms"] = cms
        result["cms_version"] = cms_version
        result["file_structure"] = self._get_file_structure(result.get("site_root_path", ""))
        result["installed_plugins"] = self._get_plugins(cms, result.get("site_root_path", ""))

        return result

    # ------------------------------------------------------------------ helpers

    def _run(self, cmd: str) -> str:
        _, stdout, _ = self._ssh.run(cmd, timeout=30)
        return stdout.strip()

    def _get_os(self) -> str:
        return self._run("lsb_release -d 2>/dev/null | cut -f2 || cat /etc/os-release | grep PRETTY_NAME | cut -d= -f2 | tr -d '\"'")

    def _get_php_version(self) -> str:
        out = self._run("php --version 2>/dev/null | head -1 || echo ''")
        if not out:
            return ""
        m = re.search(r"(\d+\.\d+\.\d+)", out)
        return m.group(1) if m else out[:20]

    def _get_web_server(self) -> str:
        # Check running processes
        nginx = self._run("nginx -v 2>&1 | head -1 || echo ''")
        if nginx and "nginx" in nginx.lower():
            m = re.search(r"(\d+\.\d+\.\d+)", nginx)
            return f"nginx {m.group(1)}" if m else "nginx"
        apache = self._run("apache2 -v 2>/dev/null | head -1 || apachectl -v 2>/dev/null | head -1 || echo ''")
        if apache and "apache" in apache.lower():
            m = re.search(r"(\d+\.\d+\.\d+)", apache)
            return f"apache {m.group(1)}" if m else "apache"
        return "unknown"

    def _get_site_root(self) -> str:
        """Try to find site root from nginx/apache config, fall back to common paths."""
        # Try nginx
        nginx_root = self._run(
            "nginx -T 2>/dev/null | grep -E '^\\s*root ' | head -1 | awk '{print $2}' | tr -d ';' || echo ''"
        )
        if nginx_root and nginx_root != "":
            return nginx_root

        # Try apache
        apache_root = self._run(
            "apache2ctl -S 2>/dev/null | grep DocumentRoot | head -1 | awk '{print $2}' || echo ''"
        )
        if apache_root and apache_root != "":
            return apache_root

        # Common locations
        for path in ["/var/www/html", "/var/www/site", "/var/www/public_html", "/srv/www/htdocs"]:
            exists = self._run(f"[ -d '{path}' ] && echo yes || echo no")
            if exists == "yes":
                return path

        return "/var/www/html"

    def _detect_cms(self, root: str) -> tuple[str, str]:
        if not root:
            return "unknown", ""

        # WordPress
        wp_config = self._run(f"[ -f '{root}/wp-config.php' ] && echo yes || echo no")
        if wp_config == "yes":
            version = self._run(
                f"grep -r '\\$wp_version\\|wp_version' {root}/wp-includes/version.php 2>/dev/null | grep -oP \"'[0-9.]+'\"|head -1|tr -d \"'\""
            )
            # Try WP CLI
            if not version:
                version = self._run(f"wp --path='{root}' core version 2>/dev/null || echo ''")
            return "wordpress", version or ""

        # Joomla
        joomla = self._run(f"[ -f '{root}/configuration.php' ] && [ -d '{root}/administrator' ] && echo yes || echo no")
        if joomla == "yes":
            version = self._run(
                f"cat {root}/libraries/cms/version/version.php 2>/dev/null | grep RELEASE | head -1 | grep -oP \"'[0-9.]+'\"|tr -d \"'\" || echo ''"
            )
            return "joomla", version or ""

        # Bitrix
        bitrix = self._run(f"[ -d '{root}/bitrix' ] && echo yes || echo no")
        if bitrix == "yes":
            return "bitrix", ""

        # Laravel
        artisan = self._run(f"[ -f '{root}/artisan' ] && echo yes || echo no")
        if artisan == "yes":
            return "laravel", ""

        # OpenCart
        opencart = self._run(f"[ -f '{root}/config.php' ] && grep -q 'opencart' {root}/config.php 2>/dev/null && echo yes || echo no")
        if opencart == "yes":
            return "opencart", ""

        return "custom", ""

    def _get_file_structure(self, root: str) -> dict:
        if not root:
            return {}
        # Get top-level dirs and key files (depth 3, max 200 entries)
        out = self._run(
            f"find '{root}' -maxdepth 3 \\( -name '*.php' -o -name '*.js' -o -name '*.css' -o -type d \\) "
            f"2>/dev/null | head -300"
        )
        files = [line for line in out.splitlines() if line.strip()]
        # Group by top-level dir
        structure: dict = {"root": root, "entries": files[:200]}
        return structure

    def _get_plugins(self, cms: str, root: str) -> dict:
        if not root:
            return {}
        if cms == "wordpress":
            out = self._run(f"ls '{root}/wp-content/plugins/' 2>/dev/null | head -50")
            plugins = [p for p in out.splitlines() if p.strip()]
            # Try to get active plugins from WP CLI
            active = self._run(f"wp --path='{root}' plugin list --status=active --field=name 2>/dev/null || echo ''")
            active_list = [p for p in active.splitlines() if p.strip()]
            return {"installed": plugins, "active": active_list}
        if cms == "joomla":
            out = self._run(f"ls '{root}/plugins/' 2>/dev/null")
            return {"groups": [p for p in out.splitlines() if p.strip()]}
        return {}
