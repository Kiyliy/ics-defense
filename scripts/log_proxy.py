"""Pikachu 靶场日志代理

反向代理 HTTP 请求到 Pikachu，同时将请求/响应记录为 JSON Lines 日志。
产出的日志格式与 PikachuCollector + normalizer.normalize_pikachu() 对齐。

环境变量:
    UPSTREAM_URL   上游 Pikachu 地址 (默认 http://pikachu:80)
    LISTEN_PORT    监听端口 (默认 8889)
    LOG_DIR        日志输出目录 (默认 /var/log/pikachu)
"""

import http.server
import json
import os
import re
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone

UPSTREAM_URL = os.environ.get("UPSTREAM_URL", "http://pikachu:80").rstrip("/")
LISTEN_PORT = int(os.environ.get("LISTEN_PORT", "8889"))
LOG_DIR = os.environ.get("LOG_DIR", "/var/log/pikachu")

os.makedirs(LOG_DIR, exist_ok=True)

# 攻击特征检测规则
ATTACK_PATTERNS = [
    ("sql_injection", re.compile(
        r"('|\"|;|--|\bor\b|\band\b|\bunion\b|\bselect\b|\bdrop\b|\binsert\b"
        r"|\bdelete\b|\bupdate\b|\bexec\b|0x[0-9a-fA-F]+|/\*.*\*/)",
        re.IGNORECASE
    )),
    ("xss", re.compile(
        r"(<script|javascript:|on\w+\s*=|<img\s|<svg\s|<iframe|alert\(|document\.|eval\()",
        re.IGNORECASE
    )),
    ("rce", re.compile(
        r"(\||\$\(|`|;)\s*(cat|ls|id|whoami|pwd|uname|nc|bash|sh|curl|wget|ping)",
        re.IGNORECASE
    )),
    ("path_traversal", re.compile(
        r"(\.\./|\.\.\\|%2e%2e|/etc/passwd|/etc/shadow|c:\\windows)",
        re.IGNORECASE
    )),
    ("file_upload", re.compile(
        r"\.(php|jsp|asp|aspx|cgi|pl|py|sh|exe|bat)\b",
        re.IGNORECASE
    )),
    ("brute_force", re.compile(
        r"(login|signin|auth|password|passwd|credential)",
        re.IGNORECASE
    )),
]

# 记录登录尝试频率，用于检测暴力破解
_login_tracker: dict[str, list[float]] = {}
BRUTE_FORCE_WINDOW = 60  # 秒
BRUTE_FORCE_THRESHOLD = 5  # 次


def detect_attack(method: str, path: str, body: str, client_ip: str) -> list[dict]:
    """检测请求中的攻击特征，返回命中的攻击类型列表"""
    full_text = f"{method} {path} {body}"
    hits = []

    for vuln_type, pattern in ATTACK_PATTERNS:
        match = pattern.search(full_text)
        if match:
            hits.append({
                "vuln_type": vuln_type,
                "matched": match.group(0)[:200],
            })

    # 暴力破解检测：短时间内同一 IP 多次登录
    if any(kw in path.lower() for kw in ("login", "auth", "signin")):
        now = time.time()
        attempts = _login_tracker.setdefault(client_ip, [])
        attempts.append(now)
        # 清理过期记录
        _login_tracker[client_ip] = [t for t in attempts if now - t < BRUTE_FORCE_WINDOW]
        if len(_login_tracker[client_ip]) >= BRUTE_FORCE_THRESHOLD:
            hits.append({
                "vuln_type": "brute_force",
                "matched": f"{len(_login_tracker[client_ip])} login attempts in {BRUTE_FORCE_WINDOW}s",
            })

    return hits


def write_log(entry: dict):
    """追加一行 JSON 到日志文件"""
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    log_path = os.path.join(LOG_DIR, f"pikachu-{date_str}.json")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


class ProxyHandler(http.server.BaseHTTPRequestHandler):
    """透明反向代理 + 攻击日志记录"""

    def _proxy(self):
        client_ip = self.client_address[0]
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8", errors="replace") if content_length > 0 else ""

        # 检测攻击
        attacks = detect_attack(self.command, self.path, body, client_ip)

        # 构建上游请求
        url = f"{UPSTREAM_URL}{self.path}"
        headers = {k: v for k, v in self.headers.items() if k.lower() not in ("host",)}
        headers["Host"] = UPSTREAM_URL.split("//", 1)[-1].split("/")[0]

        req = urllib.request.Request(
            url,
            data=body.encode("utf-8") if body else None,
            headers=headers,
            method=self.command,
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                status = resp.status
                resp_headers = dict(resp.getheaders())
                resp_body = resp.read()
        except urllib.error.HTTPError as e:
            status = e.code
            resp_headers = dict(e.headers)
            resp_body = e.read()
        except Exception as e:
            self.send_error(502, f"Upstream error: {e}")
            return

        # 转发响应
        self.send_response(status)
        for k, v in resp_headers.items():
            if k.lower() not in ("transfer-encoding", "connection"):
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(resp_body)

        # 记录攻击日志（只记录检测到攻击特征的请求）
        if attacks:
            for attack in attacks:
                entry = {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "src_ip": client_ip,
                    "dst_ip": "pikachu-web",
                    "target_ip": "pikachu-web",
                    "attacker_ip": client_ip,
                    "vuln_type": attack["vuln_type"],
                    "payload": body[:2000] if body else self.path,
                    "detail": f"{self.command} {self.path} - matched: {attack['matched']}",
                    "url": self.path,
                    "method": self.command,
                    "status_code": status,
                    "response_length": len(resp_body),
                }
                write_log(entry)
                print(f"[ATTACK] {attack['vuln_type']}: {client_ip} -> {self.path}")

    def do_GET(self):
        self._proxy()

    def do_POST(self):
        self._proxy()

    def do_PUT(self):
        self._proxy()

    def do_DELETE(self):
        self._proxy()

    def do_HEAD(self):
        self._proxy()

    def do_OPTIONS(self):
        self._proxy()

    def log_message(self, format, *args):
        pass  # 静默 HTTP 日志，只保留攻击日志


if __name__ == "__main__":
    print(f"[LOG-PROXY] Listening on :{LISTEN_PORT}, upstream={UPSTREAM_URL}")
    print(f"[LOG-PROXY] Logs -> {LOG_DIR}")
    server = http.server.HTTPServer(("0.0.0.0", LISTEN_PORT), ProxyHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[LOG-PROXY] Shutting down")
        server.shutdown()
