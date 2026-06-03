"""SiteScanner — detects CMS, PHP, web server, site root, and file structure.

Layer 1 improvement: Docker-aware scanning.
- Detects if site runs inside a Docker container
- Finds the source code directory (not dist/build artifacts)
- Stores docker_compose_dir + container_name for post-edit rebuild
"""
from __future__ import annotations

import re

from app.services.ssh.client import SSHClient


class SiteScanner:
    """Wraps SSHClient with site-level scanning logic."""

    def __init__(self, ssh: SSHClient) -> None:
        self._ssh = ssh

    def scan(self, hints: dict | None = None) -> dict:
        """Scan a single site.

        hints — optional dict from the already-known site record so we don't
        re-discover the wrong project on a multi-project server:
          - docker_compose_dir: use this compose dir instead of searching
          - site_root_path:     use this root instead of searching
          - is_docker:          skip Docker detection if already known
          - framework:          skip framework detection if already known
        """
        hints = hints or {}
        result: dict = {}
        result["server_os"] = self._get_os()
        result["php_version"] = self._get_php_version()
        result["web_server"] = self._get_web_server()

        # ── Docker detection ───────────────────────────────────────────────
        # If we already know the compose dir (user picked this project during
        # discovery), skip the server-wide search and just refresh the details
        # for that specific directory — avoids picking a neighbour project.
        known_compose_dir = hints.get("docker_compose_dir")
        known_is_docker = hints.get("is_docker")

        if known_compose_dir:
            # Scan only the known compose project, skip server-wide detection
            docker_info: dict = {
                "is_docker": True,
                "docker_compose_dir": known_compose_dir,
                "docker_container_name": None,
                "docker_service_name": None,
                "source_path": None,
                "framework": hints.get("framework"),
                "needs_rebuild": False,
            }
            score, _, service, source, framework = self._score_compose(known_compose_dir)
            if score >= 0:
                docker_info["docker_service_name"] = service
                docker_info["source_path"] = source
                docker_info["framework"] = framework or hints.get("framework")
                docker_info["needs_rebuild"] = (docker_info["framework"] or "") in (
                    "nextjs", "react", "vue", "nuxt", "vite", "angular"
                )
            result.update(docker_info)
        elif known_is_docker is False:
            # Explicitly non-Docker site. Try to detect if it's a bare-metal
            # frontend project that needs `npm run build` after source edits.
            framework = hints.get("framework")
            needs_rebuild = False
            _FRONTEND_FW = {"nextjs", "react", "vue", "nuxt", "vite", "angular"}
            if not framework or framework not in _FRONTEND_FW:
                # Try detecting from package.json at the site root (or parent of dist)
                check_root = hints.get("site_root_path", "")
                if check_root:
                    last = check_root.rstrip("/").split("/")[-1]
                    if last in ("dist", "build", ".next", "out", "public"):
                        check_root = check_root.rsplit("/", 1)[0]
                    pkg = self._run(f"cat '{check_root}/package.json' 2>/dev/null | head -50")
                    if pkg:
                        detected = self._parse_framework_from_pkg(pkg)
                        if detected in _FRONTEND_FW:
                            framework = detected
            if framework in _FRONTEND_FW:
                needs_rebuild = True
            result.update({
                "is_docker": False,
                "docker_compose_dir": None,
                "docker_container_name": None,
                "docker_service_name": None,
                "source_path": None,
                "framework": framework,
                "needs_rebuild": needs_rebuild,
            })
        else:
            # No prior info — full server-wide detection (legacy path)
            docker_info = self._detect_docker()
            result.update(docker_info)

        # ── Site root ──────────────────────────────────────────────────────
        known_root = hints.get("site_root_path")
        if known_root:
            # Trust the root from discovery; just verify it exists
            exists = self._run(f"[ -d {known_root!r} ] && echo yes || echo no")
            site_root = known_root if exists == "yes" else self._get_site_root()
        elif result.get("is_docker"):
            site_root = result.get("source_path", "") or self._get_site_root()
        else:
            site_root = self._get_site_root()

        result["site_root_path"] = site_root

        # ── CMS ────────────────────────────────────────────────────────────
        cms, cms_version = self._detect_cms(site_root)
        result["cms"] = cms
        result["cms_version"] = cms_version

        result["file_structure"] = self._get_file_structure(site_root)
        result["installed_plugins"] = self._get_plugins(cms, site_root)
        return result

    # ── Discovery: enumerate ALL sites/projects on the server ─────────────────

    def discover(self) -> list[dict]:
        """Find every site/project on the server (Docker + vhosts + web roots).

        Unlike scan(), this does not collapse to a single best candidate — it
        returns a list so the user can pick which project to work on.
        Each item: {name, url, root_path, cms, framework, is_docker,
        docker_compose_dir, docker_container_name, source_path}.
        """
        candidates: list[dict] = []
        candidates.extend(self._discover_docker())
        candidates.extend(self._discover_nginx_vhosts())
        candidates.extend(self._discover_apache_vhosts())
        candidates.extend(self._discover_fallback_dirs())

        # Dedup by root_path (Docker wins over plain web roots for the same dir)
        seen: dict[str, dict] = {}
        for c in candidates:
            key = (c.get("root_path") or c.get("docker_compose_dir") or c.get("name") or "").rstrip("/")
            if not key:
                continue
            existing = seen.get(key)
            if existing is None or (c.get("is_docker") and not existing.get("is_docker")):
                seen[key] = c
        return list(seen.values())[:30]

    def _discover_docker(self) -> list[dict]:
        """One candidate per running web service across all docker-compose files."""
        docker_ok = self._run("docker ps --format '{{.Names}}' 2>/dev/null | head -1 || echo ''")
        if not docker_ok:
            return []

        compose_paths = self._run(
            "find /root /home /srv /opt -name 'docker-compose.yml' -not -path '*/node_modules/*' "
            "2>/dev/null | head -20"
        ).splitlines()

        out: list[dict] = []
        for compose_path in compose_paths:
            compose_path = compose_path.strip()
            if not compose_path:
                continue
            compose_dir = compose_path.rsplit("/", 1)[0]
            compose_content = self._run(f"cat {compose_path} 2>/dev/null | head -200")
            if not compose_content:
                continue
            services = re.findall(r"^  (\w[\w-]*):\s*$", compose_content, re.MULTILINE)
            project = compose_dir.split("/")[-1].replace("-", "_").replace(" ", "_")
            for service in services:
                if any(x in service.lower() for x in ["db", "postgres", "redis", "mysql", "mongo", "minio", "rabbit"]):
                    continue
                container = self._run(
                    f"docker ps --format '{{{{.Names}}}}' | "
                    f"grep -E '^({project}-{service}-|{project}_{service}_)' | head -1 || echo ''"
                )
                if not container:
                    continue
                framework, source = self._detect_framework_in_container(container, compose_dir)
                out.append({
                    "name": f"{compose_dir.split('/')[-1]} / {service}",
                    "url": None,
                    "root_path": source or compose_dir,
                    "cms": framework if framework in ("wordpress", "laravel") else None,
                    "framework": framework,
                    "is_docker": True,
                    "docker_compose_dir": compose_dir,
                    "docker_container_name": container,
                    "source_path": source or compose_dir,
                })
        return out

    def _discover_nginx_vhosts(self) -> list[dict]:
        """Parse `nginx -T` server blocks → (server_name, root) pairs."""
        out_text = self._run("nginx -T 2>/dev/null || echo ''", timeout=40)
        if not out_text:
            return []

        results: list[dict] = []
        depth = 0
        in_server = False
        server_depth = 0
        names: list[str] = []
        root: str | None = None
        for raw in out_text.splitlines():
            line = raw.split("#", 1)[0].strip()
            if not line:
                continue
            if re.match(r"^server\s*\{", line) or line == "server {":
                in_server = True
                server_depth = depth
                names, root = [], None
            if in_server:
                m = re.match(r"server_name\s+(.+);", line)
                if m:
                    names = [n for n in m.group(1).split() if n and n != "_"]
                m = re.match(r"root\s+(\S+);", line)
                if m:
                    root = m.group(1)
            depth += line.count("{") - line.count("}")
            if in_server and depth <= server_depth:
                in_server = False
                if root:
                    cms, _ = self._detect_cms(root)
                    domain = names[0] if names else None
                    results.append({
                        "name": domain or root.rstrip("/").split("/")[-1],
                        "url": f"https://{domain}" if domain else None,
                        "root_path": root,
                        "cms": cms,
                        "framework": None,
                        "is_docker": False,
                        "docker_compose_dir": None,
                        "docker_container_name": None,
                        "source_path": None,
                    })
        return results

    def _discover_apache_vhosts(self) -> list[dict]:
        """Pair ServerName + DocumentRoot from apache sites-enabled configs."""
        out_text = self._run(
            "grep -rhiE 'ServerName|DocumentRoot' /etc/apache2/sites-enabled/ /etc/httpd/conf.d/ "
            "2>/dev/null || echo ''"
        )
        if not out_text:
            return []
        results: list[dict] = []
        pending_name: str | None = None
        for raw in out_text.splitlines():
            line = raw.strip()
            mn = re.match(r"(?i)ServerName\s+(\S+)", line)
            if mn:
                pending_name = mn.group(1)
                continue
            md = re.match(r"(?i)DocumentRoot\s+\"?(\S+?)\"?$", line)
            if md:
                root = md.group(1)
                cms, _ = self._detect_cms(root)
                results.append({
                    "name": pending_name or root.rstrip("/").split("/")[-1],
                    "url": f"https://{pending_name}" if pending_name else None,
                    "root_path": root,
                    "cms": cms,
                    "framework": None,
                    "is_docker": False,
                    "docker_compose_dir": None,
                    "docker_container_name": None,
                    "source_path": None,
                })
                pending_name = None
        return results

    def _discover_fallback_dirs(self) -> list[dict]:
        """Common web roots when no vhost config is parseable."""
        dirs = self._run(
            "ls -d /var/www/*/ /home/*/public_html /srv/www/*/ 2>/dev/null | head -30"
        ).splitlines()
        results: list[dict] = []
        for d in dirs:
            root = d.strip().rstrip("/")
            if not root:
                continue
            cms, _ = self._detect_cms(root)
            results.append({
                "name": root.split("/")[-1] if root.split("/")[-1] != "public_html"
                else root.split("/")[-2],
                "url": None,
                "root_path": root,
                "cms": cms,
                "framework": None,
                "is_docker": False,
                "docker_compose_dir": None,
                "docker_container_name": None,
                "source_path": None,
            })
        return results

    # ── helpers ─────────────────────────────────────────────────────────────

    def _run(self, cmd: str, timeout: int = 30) -> str:
        _, stdout, _ = self._ssh.run(cmd, timeout=timeout)
        return stdout.strip()

    def _get_os(self) -> str:
        return self._run(
            "lsb_release -d 2>/dev/null | cut -f2 || "
            "cat /etc/os-release | grep PRETTY_NAME | cut -d= -f2 | tr -d '\"'"
        )

    def _get_php_version(self) -> str:
        out = self._run("php --version 2>/dev/null | head -1 || echo ''")
        if not out:
            return ""
        m = re.search(r"(\d+\.\d+\.\d+)", out)
        return m.group(1) if m else out[:20]

    def _get_web_server(self) -> str:
        nginx = self._run("nginx -v 2>&1 | head -1 || echo ''")
        if nginx and "nginx" in nginx.lower():
            m = re.search(r"(\d+\.\d+\.\d+)", nginx)
            return f"nginx {m.group(1)}" if m else "nginx"
        apache = self._run(
            "apache2 -v 2>/dev/null | head -1 || apachectl -v 2>/dev/null | head -1 || echo ''"
        )
        if apache and "apache" in apache.lower():
            m = re.search(r"(\d+\.\d+\.\d+)", apache)
            return f"apache {m.group(1)}" if m else "apache"
        return "unknown"

    # ── Docker detection ─────────────────────────────────────────────────────

    def _detect_docker(self) -> dict:
        """Detect Docker-based sites and find their source directories."""
        result: dict = {
            "is_docker": False,
            "docker_compose_dir": None,
            "docker_container_name": None,
            "docker_service_name": None,
            "source_path": None,
            "framework": None,       # nextjs | react | vue | nuxt | laravel | ...
            "needs_rebuild": False,
        }

        docker_ok = self._run("docker ps --format '{{.Names}}' 2>/dev/null | head -1 || echo ''")
        if not docker_ok:
            return result

        result["is_docker"] = True

        # 1. Find all docker-compose.yml files on the server
        compose_dirs = self._run(
            "find /root /home /srv /opt -name 'docker-compose.yml' -not -path '*/node_modules/*' "
            "2>/dev/null | head -20"
        ).splitlines()

        best_dir = None
        best_score = -1
        found_container = None
        found_service = None
        found_source = None
        found_framework = None

        for compose_path in compose_dirs:
            compose_path = compose_path.strip()
            if not compose_path:
                continue
            compose_dir = compose_path.rsplit("/", 1)[0]
            score, container, service, source, framework = self._score_compose(compose_dir)
            if score > best_score:
                best_score = score
                best_dir = compose_dir
                found_container = container
                found_service = service
                found_source = source
                found_framework = framework

        if best_dir and best_score >= 0:
            result["docker_compose_dir"] = best_dir
            result["docker_container_name"] = found_container
            result["docker_service_name"] = found_service
            result["source_path"] = found_source
            result["framework"] = found_framework
            result["needs_rebuild"] = found_framework in (
                "nextjs", "react", "vue", "nuxt", "vite", "angular"
            )

        return result

    def _score_compose(self, compose_dir: str) -> tuple[int, str | None, str | None, str | None, str | None]:
        """Score a docker-compose dir: return (score, container, service, source_path, framework)."""
        # Read compose file to find web-like services
        compose_content = self._run(f"cat {compose_dir}/docker-compose.yml 2>/dev/null | head -200")
        if not compose_content:
            return -1, None, None, None, None

        # Extract service names from compose
        services = re.findall(r"^  (\w[\w-]*):\s*$", compose_content, re.MULTILINE)

        best_service = None
        best_source = None
        best_framework = None
        best_score = -1

        for service in services:
            # Skip infra services
            if any(x in service.lower() for x in ["db", "postgres", "redis", "mysql", "mongo", "minio", "rabbit"]):
                continue

            # Find running container for this service
            project = compose_dir.split("/")[-1].replace("-", "_").replace(" ", "_")
            container_name = self._run(
                f"docker ps --format '{{{{.Names}}}}' | grep -E '^({project}-{service}-|{project}_{service}_)' | head -1 || echo ''"
            )
            if not container_name:
                continue

            # Detect framework from container
            framework, source = self._detect_framework_in_container(container_name, compose_dir)
            score = self._framework_score(framework)
            if score > best_score:
                best_score = score
                best_service = service
                best_source = source
                best_framework = framework

        return best_score, None, best_service, best_source, best_framework

    def _detect_framework_in_container(self, container: str, compose_dir: str) -> tuple[str, str]:
        """Detect framework and source path for a container."""
        # Check package.json inside container
        pkg = self._run(f"docker exec {container} cat /app/package.json 2>/dev/null || "
                        f"docker exec {container} cat /usr/src/app/package.json 2>/dev/null || echo ''")
        if pkg:
            framework = self._parse_framework_from_pkg(pkg)
            # Source path: look for mounted src/ in compose_dir
            src_path = self._find_source_in_compose_dir(compose_dir, container)
            return framework, src_path or compose_dir

        # Check if it's PHP/Laravel
        artisan = self._run(f"docker exec {container} test -f /var/www/artisan && echo yes || echo no 2>/dev/null")
        if artisan == "yes":
            src_path = self._find_source_in_compose_dir(compose_dir, container)
            return "laravel", src_path or compose_dir

        # Check if it's WordPress
        wp = self._run(f"docker exec {container} test -f /var/www/html/wp-config.php && echo yes || echo no 2>/dev/null")
        if wp == "yes":
            return "wordpress", compose_dir

        return "unknown", compose_dir

    def _parse_framework_from_pkg(self, pkg_json: str) -> str:
        pkg_lower = pkg_json.lower()
        if '"next"' in pkg_lower:
            return "nextjs"
        if '"nuxt"' in pkg_lower:
            return "nuxt"
        if '"@angular/core"' in pkg_lower:
            return "angular"
        if '"vue"' in pkg_lower:
            return "vue"
        if '"react"' in pkg_lower:
            return "react"
        if '"vite"' in pkg_lower:
            return "vite"
        return "node"

    def _find_source_in_compose_dir(self, compose_dir: str, container: str) -> str | None:
        """Find source code directory — prefer src/ over dist/build."""
        # Look for src/ directory with source files
        candidates = [
            f"{compose_dir}/src",
            f"{compose_dir}/app",
        ]
        # Also look in subdirs (e.g. /root/cvguru/apps/cvguru/web/)
        subdirs = self._run(
            f"find {compose_dir} -maxdepth 4 -name 'package.json' "
            f"-not -path '*/node_modules/*' -not -path '*/dist/*' 2>/dev/null"
        ).splitlines()
        for pkg_path in subdirs:
            pkg_path = pkg_path.strip()
            if pkg_path:
                candidates.insert(0, pkg_path.rsplit("/", 1)[0])

        for path in candidates:
            exists = self._run(f"[ -d '{path}' ] && echo yes || echo no")
            if exists == "yes":
                # Prefer directories with src/ or app/ inside them
                has_src = self._run(f"[ -d '{path}/src' ] || [ -d '{path}/app' ] && echo yes || echo no")
                if has_src == "yes":
                    return path
                return path
        return None

    def _framework_score(self, framework: str) -> int:
        scores = {
            "nextjs": 10, "nuxt": 9, "react": 8, "vue": 8,
            "vite": 7, "angular": 7, "laravel": 6,
            "node": 3, "wordpress": 5, "unknown": 0,
        }
        return scores.get(framework, 0)

    # ── Site root (non-Docker fallback) ───────────────────────────────────────

    def _get_site_root(self) -> str:
        nginx_root = self._run(
            "nginx -T 2>/dev/null | grep -E '^\\s*root ' | head -1 | awk '{print $2}' | tr -d ';' || echo ''"
        )
        if nginx_root:
            return self._resolve_source_root(nginx_root)
        apache_root = self._run(
            "apache2ctl -S 2>/dev/null | grep DocumentRoot | head -1 | awk '{print $2}' || echo ''"
        )
        if apache_root:
            return self._resolve_source_root(apache_root)
        for path in ["/var/www/html", "/var/www/site", "/var/www/public_html"]:
            if self._run(f"[ -d '{path}' ] && echo yes || echo no") == "yes":
                return path
        return "/var/www/html"

    def _resolve_source_root(self, root: str) -> str:
        """If root points to a build output dir (dist/build/.next), return the source root instead."""
        root = root.rstrip("/")
        last = root.split("/")[-1]
        if last not in ("dist", "build", ".next", "public", "out"):
            return root
        parent = root.rsplit("/", 1)[0]
        # Prefer parent if it has a package.json (JS project source root)
        has_pkg = self._run(f"[ -f '{parent}/package.json' ] && echo yes || echo no")
        if has_pkg == "yes":
            return parent
        # Or src/ sibling
        has_src = self._run(f"[ -d '{parent}/src' ] && echo yes || echo no")
        if has_src == "yes":
            return parent
        return root

    # ── CMS ───────────────────────────────────────────────────────────────────

    def _detect_cms(self, root: str) -> tuple[str, str]:
        if not root:
            return "unknown", ""
        if self._run(f"[ -f '{root}/wp-config.php' ] && echo yes || echo no") == "yes":
            version = self._run(
                f"grep -r '\\$wp_version' {root}/wp-includes/version.php 2>/dev/null | "
                f"grep -oP \"'[0-9.]+'\"|head -1|tr -d \"'\"")
            if not version:
                version = self._run(f"wp --path='{root}' core version 2>/dev/null || echo ''")
            return "wordpress", version or ""
        if self._run(f"[ -f '{root}/configuration.php' ] && [ -d '{root}/administrator' ] && echo yes || echo no") == "yes":
            return "joomla", ""
        if self._run(f"[ -d '{root}/bitrix' ] && echo yes || echo no") == "yes":
            return "bitrix", ""
        if self._run(f"[ -f '{root}/artisan' ] && echo yes || echo no") == "yes":
            return "laravel", ""
        if self._run(f"[ -f '{root}/config.php' ] && grep -q 'opencart' {root}/config.php 2>/dev/null && echo yes || echo no") == "yes":
            return "opencart", ""
        # Check for Next.js / React in source
        if self._run(f"[ -f '{root}/next.config.ts' ] || [ -f '{root}/next.config.js' ] && echo yes || echo no") == "yes":
            return "nextjs", ""
        if self._run(f"[ -f '{root}/package.json' ] && echo yes || echo no") == "yes":
            pkg = self._run(f"cat {root}/package.json 2>/dev/null | head -50")
            if '"next"' in pkg:
                return "nextjs", ""
            if '"nuxt"' in pkg:
                return "nuxt", ""
            if '"vue"' in pkg:
                return "vue", ""
            if '"vite"' in pkg:
                return "vite", ""
            if '"react"' in pkg:
                return "react", ""
        return "custom", ""

    # ── File structure ─────────────────────────────────────────────────────────

    def _get_file_structure(self, root: str) -> dict:
        if not root:
            return {}
        out = self._run(
            f"find '{root}' -maxdepth 6 "
            f"-not -path '*/node_modules/*' -not -path '*/.git/*' "
            f"-not -path '*/__pycache__/*' -not -name '*.pyc' "
            f"2>/dev/null | sort | head -600"
        )
        files = [line for line in out.splitlines() if line.strip()]
        return {"root": root, "entries": files[:500]}

    # ── Plugins ───────────────────────────────────────────────────────────────

    def _get_plugins(self, cms: str, root: str) -> dict:
        if not root:
            return {}
        if cms == "wordpress":
            plugins = [p for p in self._run(f"ls '{root}/wp-content/plugins/' 2>/dev/null | head -50").splitlines() if p.strip()]
            active = [p for p in self._run(f"wp --path='{root}' plugin list --status=active --field=name 2>/dev/null || echo ''").splitlines() if p.strip()]
            return {"installed": plugins, "active": active}
        if cms == "joomla":
            return {"groups": [p for p in self._run(f"ls '{root}/plugins/' 2>/dev/null").splitlines() if p.strip()]}
        return {}
