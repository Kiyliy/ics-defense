# 靶场环境部署与使用指南

## 概述

本项目集成了 Pikachu 漏洞靶场作为攻防演练环境，用于生成真实攻击日志，验证「采集 → 归一化 → AI 分析 → 响应」的完整链路。

靶场架构如下：

```
攻击脚本 ──→ 日志代理 (:8889) ──→ Pikachu 靶场 (:8888)
                │
                ▼
        range-logs/pikachu/
          (JSON Lines 日志)
                │
                ▼
        PikachuCollector 采集
                │
                ▼
        Normalizer → Clusterer → Agent
```

## 环境要求

- Docker + Docker Compose
- Python 3.10+（运行攻击脚本）

## 快速启动

```bash
# 1. 启动靶场容器
docker compose -f docker-compose.range.yml up -d

# 2. 等待 Pikachu 内置 MySQL 初始化（约 30 秒）
#    可通过日志查看进度：
docker logs -f pikachu-web

# 3. 初始化 Pikachu 数据库（仅首次需要）
curl -X POST "http://localhost:8888/install.php" \
  -d "submit=%E5%AE%89%E8%A3%85%2F%E5%88%9D%E5%A7%8B%E5%8C%96"

# 4. 验证靶场可访问
curl -s -o /dev/null -w "%{http_code}" http://localhost:8888/
# 应返回 200
```

## 运行攻击脚本

攻击脚本通过日志代理（端口 8889）访问靶场，代理会自动检测攻击特征并记录日志。

```bash
# 默认 1 轮攻击
python3 scripts/attack_pikachu.py

# 指定 3 轮攻击
python3 scripts/attack_pikachu.py --rounds 3

# 指定目标地址（如代理部署在远程机器上）
python3 scripts/attack_pikachu.py --target http://192.168.1.100:8889 --rounds 2
```

### 攻击类型覆盖

| 攻击类型 | 载荷数量 | Pikachu 漏洞模块 | MITRE ATT&CK 映射 |
|----------|---------|------------------|-------------------|
| SQL 注入 | 16 | sqli_str, sqli_id | T0807 Execution |
| XSS | 15 | xss_reflected, xss_stored | T0807 Execution |
| RCE 命令执行 | 12 | rce_ping, rce_eval | T0807 Execution |
| 目录遍历 | 8 | fi_local, fi_remote | T0846 Reconnaissance |
| 暴力破解 | 12 | bf_form | T0866 Initial Access |
| 恶意文件上传 | 4 | clientcheck | T0839 Persistence |

## 日志格式

日志以 JSON Lines 格式写入 `range-logs/pikachu/` 目录，每天一个文件。

文件命名：`pikachu-YYYY-MM-DD.json`

单条日志示例：

```json
{
  "timestamp": "2026-03-09T05:32:15.504986+00:00",
  "src_ip": "192.168.144.1",
  "dst_ip": "pikachu-web",
  "target_ip": "pikachu-web",
  "attacker_ip": "192.168.144.1",
  "vuln_type": "sql_injection",
  "payload": "' OR '1'='1' -- ",
  "detail": "GET /vul/sqli/sqli_str.php?name=... - matched: --",
  "url": "/vul/sqli/sqli_str.php?name=...",
  "method": "GET",
  "status_code": 200,
  "response_length": 34097
}
```

字段与 `collector/normalizer.py` 中 `normalize_pikachu()` 的输入字段对齐：
- `vuln_type` → 告警标题
- `payload` → 告警描述
- `src_ip` / `attacker_ip` → 攻击源 IP
- `dst_ip` / `target_ip` → 目标 IP

## 对接 PikachuCollector

将 PikachuCollector 的 `watch_dir` 指向日志输出目录即可：

```python
from collector.sources.pikachu_collector import PikachuCollector

collector = PikachuCollector(config={
    "watch_dir": "./range-logs/pikachu/",  # 靶场日志目录
    "poll_interval": 5,
})
```

## 端口说明

| 端口 | 服务 | 用途 |
|------|------|------|
| 8888 | Pikachu 靶场 | 直连访问，可用浏览器打开练习 |
| 8889 | 日志代理 | 攻击流量入口，自动记录攻击日志 |

## 常用命令

```bash
# 查看容器状态
docker compose -f docker-compose.range.yml ps

# 查看代理日志
docker logs -f pikachu-logger

# 查看已生成的攻击日志条数
wc -l range-logs/pikachu/*.json

# 按攻击类型统计
cat range-logs/pikachu/*.json | python3 -c "
import json, sys, collections
c = collections.Counter()
for line in sys.stdin:
    c[json.loads(line)['vuln_type']] += 1
for t, n in c.most_common():
    print(f'  {t:<20} {n}')
"

# 停止靶场
docker compose -f docker-compose.range.yml down

# 清理日志重新测试
rm -f range-logs/pikachu/*.json
```
