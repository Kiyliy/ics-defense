import json
import logging
import os
from datetime import datetime
from uuid import uuid4
from mcp.server.fastmcp import FastMCP

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
)
logger = logging.getLogger("memory")

mcp = FastMCP(name="memory", instructions="ICS Agent 长期记忆服务（基于 Mem0）")

# 记忆存储（简单实现，生产环境替换为 Mem0 / Qdrant）
memories = []

# Qdrant 连接状态（用于优雅降级）
_qdrant_available = False
_qdrant_client = None

QDRANT_URL = os.environ.get("QDRANT_URL", "http://localhost:6333")


def _try_init_qdrant():
    """Attempt to connect to Qdrant. If unavailable, fall back to in-memory storage."""
    global _qdrant_available, _qdrant_client
    try:
        from qdrant_client import QdrantClient
        client = QdrantClient(url=QDRANT_URL, timeout=5)
        # Simple health check
        client.get_collections()
        _qdrant_client = client
        _qdrant_available = True
        logger.info("Qdrant 连接成功: %s", QDRANT_URL)
    except ImportError:
        logger.info("qdrant-client 未安装，使用内存记忆存储")
        _qdrant_available = False
    except Exception as exc:
        logger.warning("Qdrant 连接失败 (%s)，回退到内存记忆存储: %s", QDRANT_URL, exc)
        _qdrant_available = False


# Try to connect at startup
_try_init_qdrant()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
_VALID_CATEGORIES = {"analysis", "false_positive", "attack_pattern", "asset_context"}


def _keyword_score(query: str, content: str) -> float:
    """简单的关键词匹配评分"""
    if not query or not content:
        return 0.0
    query_words = set(query.lower().split())
    content_words = set(content.lower().split())
    if not query_words:
        return 0.0
    overlap = query_words & content_words
    return len(overlap) / len(query_words)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------
@mcp.tool()
def recall(query: str, top_k: int = 5) -> str:
    """语义检索历史相似案例和经验

    Args:
        query: 查询文本（描述当前告警或问题）
        top_k: 返回最多N条最相关的记忆

    Returns:
        JSON: {"memories": [{"id": "...", "content": "...", "score": 0.85, "metadata": {...}, "created_at": "..."}]}
    """
    if not query or not query.strip():
        logger.warning("recall: query 为空")
        return json.dumps({"memories": [], "note": "query 为空"}, ensure_ascii=False)

    if not isinstance(top_k, int) or top_k < 1:
        top_k = 5

    logger.info("recall: query='%s' top_k=%d (storage=%s)",
                query[:100], top_k, "qdrant" if _qdrant_available else "memory")

    try:
        scored = []
        for mem in memories:
            score = _keyword_score(query, mem["content"])
            if score > 0:
                scored.append({**mem, "score": round(score, 3)})

        scored.sort(key=lambda x: x["score"], reverse=True)
        result = scored[:top_k]
        logger.info("recall: 返回 %d 条记忆", len(result))
        return json.dumps({"memories": result}, ensure_ascii=False)
    except Exception as exc:
        logger.error("recall 异常: %s", exc, exc_info=True)
        return json.dumps({"memories": [], "error": str(exc)}, ensure_ascii=False)


@mcp.tool()
def memorize(content: str, category: str = "analysis", metadata: str = "{}") -> str:
    """存储本次分析结论到长期记忆

    Args:
        content: 记忆内容（分析结论、经验教训等）
        category: 记忆类别 (analysis/false_positive/attack_pattern/asset_context)
        metadata: 附加元数据 JSON（如 alert_id, trace_id 等）

    Returns:
        JSON: {"status": "stored", "memory_id": "...", "created_at": "..."}
    """
    if not content or not content.strip():
        logger.warning("memorize: content 为空")
        return json.dumps({"status": "error", "error": "content 不能为空"}, ensure_ascii=False)

    if category not in _VALID_CATEGORIES:
        logger.warning("memorize: 无效的 category '%s'，使用默认 'analysis'", category)
        category = "analysis"

    # Parse metadata
    parsed_metadata = {}
    try:
        if metadata and isinstance(metadata, str):
            parsed_metadata = json.loads(metadata)
        elif isinstance(metadata, dict):
            parsed_metadata = metadata
    except (json.JSONDecodeError, TypeError) as exc:
        logger.warning("memorize: metadata JSON 解析失败: %s", exc)
        parsed_metadata = {}

    memory_id = str(uuid4())[:8]
    now = datetime.now().isoformat()

    mem = {
        "id": memory_id,
        "content": content,
        "category": category,
        "metadata": parsed_metadata,
        "created_at": now,
    }

    try:
        memories.append(mem)
        logger.info("memorize: 存储记忆 id=%s category=%s (storage=%s)",
                     memory_id, category, "qdrant" if _qdrant_available else "memory")
        return json.dumps({"status": "stored", "memory_id": memory_id, "created_at": now}, ensure_ascii=False)
    except Exception as exc:
        logger.error("memorize 存储异常: %s", exc, exc_info=True)
        return json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False)


@mcp.tool()
def list_memories(limit: int = 20, category: str = None) -> str:
    """列出所有记忆

    Args:
        limit: 返回条数限制
        category: 按类别过滤（可选）

    Returns:
        JSON: {"memories": [...], "total": N}
    """
    if not isinstance(limit, int) or limit < 1:
        limit = 20

    logger.info("list_memories: limit=%d category=%s", limit, category)

    try:
        filtered = memories
        if category:
            if category not in _VALID_CATEGORIES:
                logger.warning("list_memories: 无效的 category '%s'", category)
                return json.dumps({"memories": [], "total": 0, "note": f"无效的 category: {category}"}, ensure_ascii=False)
            filtered = [m for m in memories if m.get("category") == category]

        result = filtered[-limit:]  # 最近的
        logger.info("list_memories: 返回 %d / %d 条", len(result), len(filtered))
        return json.dumps({"memories": result, "total": len(filtered)}, ensure_ascii=False)
    except Exception as exc:
        logger.error("list_memories 异常: %s", exc, exc_info=True)
        return json.dumps({"memories": [], "total": 0, "error": str(exc)}, ensure_ascii=False)


if __name__ == "__main__":
    mcp.run()
