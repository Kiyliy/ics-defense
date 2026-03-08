import pytest
import asyncio
from agent.memory import AgentMemory, SimpleMemory


@pytest.fixture
def memory():
    return AgentMemory({"provider": "simple"})


@pytest.fixture
def simple_store():
    return SimpleMemory()


@pytest.mark.asyncio
async def test_memorize(memory):
    """存储一条记忆，返回 memory_id"""
    mid = await memory.memorize("发现 10.0.0.5 进行端口扫描，判定为真实攻击")
    assert mid is not None
    assert isinstance(mid, str)
    assert len(mid) > 0


@pytest.mark.asyncio
async def test_recall(memory):
    """存储后检索，关键词匹配返回结果"""
    await memory.memorize("发现 10.0.0.5 进行端口扫描，判定为真实攻击")
    await memory.memorize("WAF 拦截了 SQL 注入攻击，来源 192.168.1.100")

    results = await memory.recall("端口扫描 10.0.0.5")
    assert len(results) > 0
    assert any("端口扫描" in r["content"] for r in results)
    # 每条结果应该有必要字段
    for r in results:
        assert "id" in r
        assert "content" in r
        assert "score" in r
        assert "created_at" in r


@pytest.mark.asyncio
async def test_recall_no_match(memory):
    """检索无关内容，返回空列表"""
    await memory.memorize("发现 10.0.0.5 进行端口扫描")
    results = await memory.recall("完全无关的查询词汇xyz")
    assert len(results) == 0


@pytest.mark.asyncio
async def test_list_memories(memory):
    """存储多条后 list_memories 返回正确数量"""
    await memory.memorize("记忆1")
    await memory.memorize("记忆2")
    await memory.memorize("记忆3")

    all_mems = await memory.list_memories()
    assert len(all_mems) == 3

    # 测试 limit
    limited = await memory.list_memories(limit=2)
    assert len(limited) == 2


@pytest.mark.asyncio
async def test_delete(memory):
    """删除后再检索找不到"""
    mid = await memory.memorize("临时记忆 端口扫描攻击")

    # 确认存在
    results = await memory.recall("端口扫描")
    assert len(results) > 0

    # 删除
    deleted = await memory.delete(mid)
    assert deleted is True

    # 再次检索
    results = await memory.recall("端口扫描")
    assert len(results) == 0

    # 删除不存在的
    deleted = await memory.delete("nonexistent-id")
    assert deleted is False


@pytest.mark.asyncio
async def test_simple_memory_scoring(simple_store):
    """SimpleMemory 的关键词评分逻辑"""
    await simple_store.add("端口扫描攻击来自 10.0.0.5 的恶意行为")
    await simple_store.add("SQL注入攻击被WAF拦截")
    await simple_store.add("正常的系统维护操作日志")

    # 搜索 "端口扫描 攻击"，第一条应该得分最高
    results = await simple_store.search("端口扫描 攻击")
    assert len(results) >= 1
    # 包含更多关键词的记忆得分更高
    top_result = results[0]
    assert "端口扫描" in top_result["content"]
    assert top_result["score"] > 0


@pytest.mark.asyncio
async def test_memorize_with_metadata(memory):
    """存储带 metadata 的记忆"""
    mid = await memory.memorize(
        "分析结论：10.0.0.5 为攻击者",
        metadata={"alert_id": "alert-001", "category": "攻击模式"}
    )
    all_mems = await memory.list_memories()
    assert len(all_mems) == 1
    assert all_mems[0]["metadata"]["alert_id"] == "alert-001"
    assert all_mems[0]["metadata"]["category"] == "攻击模式"


@pytest.mark.asyncio
async def test_default_provider():
    """默认 provider 是 simple"""
    mem = AgentMemory()
    assert mem.provider == "simple"
    assert isinstance(mem._store, SimpleMemory)


@pytest.mark.asyncio
async def test_mem0_provider_falls_back_to_safe_in_memory_store():
    mem = AgentMemory({"provider": "mem0", "mem0_config": {"region": "test"}})

    assert mem.provider == "mem0"
    assert getattr(mem._store, "backend", None) in {"mem0", "simple-fallback"}

    memory_id = await mem.memorize("mem0 fallback content", metadata={"trace_id": "t-1"})
    results = await mem.recall("fallback content")

    assert isinstance(memory_id, str) and memory_id
    assert any(item["content"] == "mem0 fallback content" for item in results)
