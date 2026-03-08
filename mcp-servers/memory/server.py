import json
import os
import hashlib
from datetime import datetime
from uuid import uuid4
from mcp.server.fastmcp import FastMCP

mcp = FastMCP(name="memory", instructions="ICS Agent 长期记忆服务（基于 Mem0）")

# 记忆存储（简单实现，生产环境替换为 Mem0）
memories = []

def _keyword_score(query: str, content: str) -> float:
    """简单的关键词匹配评分"""
    query_words = set(query.lower().split())
    content_words = set(content.lower().split())
    if not query_words:
        return 0.0
    overlap = query_words & content_words
    return len(overlap) / len(query_words)

@mcp.tool()
def recall(query: str, top_k: int = 5) -> str:
    """语义检索历史相似案例和经验

    Args:
        query: 查询文本（描述当前告警或问题）
        top_k: 返回最多N条最相关的记忆

    Returns:
        JSON: {"memories": [{"id": "...", "content": "...", "score": 0.85, "metadata": {...}, "created_at": "..."}]}
    """
    scored = []
    for mem in memories:
        score = _keyword_score(query, mem["content"])
        if score > 0:
            scored.append({**mem, "score": round(score, 3)})

    scored.sort(key=lambda x: x["score"], reverse=True)
    return json.dumps({"memories": scored[:top_k]}, ensure_ascii=False)

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
    memory_id = str(uuid4())[:8]
    mem = {
        "id": memory_id,
        "content": content,
        "category": category,
        "metadata": (json.loads(metadata) if isinstance(metadata, str) else metadata) if metadata else {},
        "created_at": datetime.now().isoformat()
    }
    memories.append(mem)
    return json.dumps({"status": "stored", "memory_id": memory_id, "created_at": mem["created_at"]}, ensure_ascii=False)

@mcp.tool()
def list_memories(limit: int = 20, category: str = None) -> str:
    """列出所有记忆

    Args:
        limit: 返回条数限制
        category: 按类别过滤（可选）

    Returns:
        JSON: {"memories": [...], "total": N}
    """
    filtered = memories
    if category:
        filtered = [m for m in memories if m.get("category") == category]

    result = filtered[-limit:]  # 最近的
    return json.dumps({"memories": result, "total": len(filtered)}, ensure_ascii=False)

if __name__ == "__main__":
    mcp.run()
