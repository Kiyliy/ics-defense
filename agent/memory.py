import uuid
from datetime import datetime, timezone


class AgentMemory:
    """Agent 长期记忆管理（基于 Mem0）"""

    def __init__(self, config: dict = None):
        """
        config 示例:
        {
            "provider": "mem0",  # 或 "simple"（内存版，用于测试）
            "mem0_config": { ... }
        }
        如果 provider == "simple"，使用 SimpleMemory（内存列表 + 简单关键词匹配）
        如果 provider == "mem0"，使用 Mem0 库
        """
        self.provider = (config or {}).get("provider", "simple")
        if self.provider == "simple":
            self._store = SimpleMemory()
        else:
            self._store = Mem0Memory((config or {}).get("mem0_config", {}))

    async def recall(self, query: str, top_k: int = 5) -> list[dict]:
        """检索与 query 相关的历史记忆
        返回: [{"id": "...", "content": "...", "score": 0.85, "created_at": "..."}, ...]
        """
        return await self._store.search(query, top_k)

    async def memorize(self, content: str, metadata: dict = None) -> str:
        """存储一条新记忆
        metadata 可包含: alert_id, trace_id, category(分析经验/误报记录/攻击模式/资产上下文)
        返回: memory_id
        """
        return await self._store.add(content, metadata)

    async def list_memories(self, limit: int = 20) -> list[dict]:
        """列出所有记忆（分页）"""
        return await self._store.list_all(limit)

    async def delete(self, memory_id: str) -> bool:
        """删除一条记忆"""
        return await self._store.remove(memory_id)


class SimpleMemory:
    """简单内存记忆实现（用于测试和开发）"""

    def __init__(self):
        self.memories = []  # [{"id": uuid, "content": str, "metadata": dict, "created_at": str}]

    async def search(self, query: str, top_k: int = 5) -> list:
        """简单关键词匹配（不是向量搜索）
        对每条记忆计算 query 中关键词的命中率作为 score
        """
        if not self.memories:
            return []

        query_keywords = set(query.lower().split())
        if not query_keywords:
            return []

        scored = []
        for mem in self.memories:
            content_lower = mem["content"].lower()
            hits = sum(1 for kw in query_keywords if kw in content_lower)
            score = hits / len(query_keywords)
            if score > 0:
                scored.append({
                    "id": mem["id"],
                    "content": mem["content"],
                    "score": round(score, 4),
                    "created_at": mem["created_at"],
                })

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]

    async def add(self, content: str, metadata: dict = None) -> str:
        """添加记忆"""
        memory_id = str(uuid.uuid4())
        self.memories.append({
            "id": memory_id,
            "content": content,
            "metadata": metadata or {},
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        return memory_id

    async def list_all(self, limit: int = 20) -> list:
        """列出所有"""
        return [
            {
                "id": m["id"],
                "content": m["content"],
                "metadata": m["metadata"],
                "created_at": m["created_at"],
            }
            for m in self.memories[:limit]
        ]

    async def remove(self, memory_id: str) -> bool:
        """删除"""
        for i, mem in enumerate(self.memories):
            if mem["id"] == memory_id:
                self.memories.pop(i)
                return True
        return False


class Mem0Memory:
    """Mem0 实现（生产环境用）"""

    def __init__(self, config: dict):
        # from mem0 import Memory
        # self.m = Memory.from_config(config)
        self.config = config

    async def search(self, query: str, top_k: int = 5) -> list:
        """检索记忆"""
        pass

    async def add(self, content: str, metadata: dict = None) -> str:
        """添加记忆"""
        pass

    async def list_all(self, limit: int = 20) -> list:
        """列出所有"""
        pass

    async def remove(self, memory_id: str) -> bool:
        """删除"""
        pass
