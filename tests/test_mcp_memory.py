import json
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'mcp-servers'))

from memory.server import memorize, recall, list_memories, memories


@pytest.fixture(autouse=True)
def clear_memories():
    memories.clear()
    yield
    memories.clear()


def test_memorize():
    """存储一条记忆 -> 返回 memory_id"""
    result = json.loads(memorize(content="发现端口扫描攻击"))
    assert result["status"] == "stored"
    assert "memory_id" in result
    assert len(result["memory_id"]) > 0
    assert "created_at" in result


def test_recall_match():
    """存储后查询匹配关键词 -> 返回匹配结果"""
    memorize(content="SQL注入攻击 10.0.0.5")
    result = json.loads(recall(query="SQL注入攻击"))
    assert len(result["memories"]) > 0
    assert "SQL注入攻击" in result["memories"][0]["content"]


def test_recall_no_match():
    """查询无关内容 -> 返回空 memories"""
    memorize(content="端口扫描攻击检测")
    result = json.loads(recall(query="completely_unrelated_xyz"))
    assert len(result["memories"]) == 0


def test_recall_top_k():
    """存储多条, top_k=2 -> 最多返回 2 条"""
    memorize(content="attack pattern alpha bravo")
    memorize(content="attack pattern charlie delta")
    memorize(content="attack pattern echo foxtrot")
    result = json.loads(recall(query="attack pattern", top_k=2))
    assert len(result["memories"]) <= 2


def test_list_memories():
    """存储多条 -> list_memories 返回正确数量"""
    memorize(content="记忆1")
    memorize(content="记忆2")
    memorize(content="记忆3")
    result = json.loads(list_memories())
    assert result["total"] == 3
    assert len(result["memories"]) == 3


def test_list_memories_by_category():
    """按 category 过滤"""
    memorize(content="分析结论A", category="analysis")
    memorize(content="误报记录B", category="false_positive")
    memorize(content="分析结论C", category="analysis")

    result = json.loads(list_memories(category="analysis"))
    assert result["total"] == 2
    assert all(m["category"] == "analysis" for m in result["memories"])

    result_fp = json.loads(list_memories(category="false_positive"))
    assert result_fp["total"] == 1


def test_memorize_with_metadata():
    """存储时附加 metadata，list 时能看到"""
    meta = json.dumps({"alert_id": "alert-001", "trace_id": "t-123"})
    memorize(content="攻击模式记录", category="attack_pattern", metadata=meta)

    result = json.loads(list_memories())
    assert len(result["memories"]) == 1
    mem = result["memories"][0]
    assert mem["metadata"]["alert_id"] == "alert-001"
    assert mem["metadata"]["trace_id"] == "t-123"
    assert mem["category"] == "attack_pattern"


def test_recall_scoring():
    """多条记忆，查询时按相关度排序"""
    memorize(content="SQL注入 攻击 来自 外网")
    memorize(content="端口扫描 攻击 内网探测")
    memorize(content="SQL注入 攻击 数据库 泄露 外网")

    result = json.loads(recall(query="SQL注入 攻击 外网"))
    mems = result["memories"]
    assert len(mems) >= 2
    # 第一条得分应 >= 第二条（包含更多匹配词）
    assert mems[0]["score"] >= mems[1]["score"]
