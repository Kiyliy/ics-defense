from __future__ import annotations

import pytest

from agent.memory import AgentMemory, SimpleMemory


@pytest.mark.asyncio
async def test_simple_memory_search_respects_top_k_and_score_order():
    store = SimpleMemory()
    await store.add('sql injection attack from 10.0.0.1')
    await store.add('sql injection observed repeatedly')
    await store.add('normal maintenance log entry')

    results = await store.search('sql injection attack', top_k=1)

    assert len(results) == 1
    assert 'attack' in results[0]['content']
    assert results[0]['score'] >= 0.66


@pytest.mark.asyncio
async def test_simple_memory_blank_query_returns_empty():
    store = SimpleMemory()
    await store.add('anything useful')

    assert await store.search('   ') == []


@pytest.mark.asyncio
async def test_agent_memory_non_simple_provider_delegates_to_mem0_stub():
    memory = AgentMemory({'provider': 'mem0', 'mem0_config': {'region': 'test'}})

    assert memory.provider == 'mem0'
    assert await memory.recall('threat') is None
    assert await memory.memorize('content') is None
    assert await memory.list_memories() is None
    assert await memory.delete('id') is None
