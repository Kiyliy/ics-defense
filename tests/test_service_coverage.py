from __future__ import annotations

import asyncio
import json
import sqlite3
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from agent import service


SCHEMA_SQL = Path('tests/conftest.py').read_text(encoding='utf-8').split('SCHEMA_SQL = """', 1)[1].split('"""', 1)[0]


class DummyMCPClient:
    def __init__(self):
        self.close = AsyncMock()
        self.connect_all = AsyncMock()
        self.refresh_tools = AsyncMock()

    def get_connected_servers(self):
        return ['memory', 'rule-engine']


@pytest.fixture
def service_db_path(tmp_path: Path) -> str:
    db_path = str(tmp_path / 'service-coverage.db')
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    conn.close()
    return db_path


@pytest.fixture
def client(monkeypatch, service_db_path: str):
    old_db_path = service.DB_PATH
    old_tasks = dict(service._running_tasks)
    old_mcp = service._mcp_client
    service._running_tasks.clear()
    monkeypatch.setattr(service, 'DB_PATH', service_db_path)
    monkeypatch.setattr(service, '_mcp_client', None)
    monkeypatch.setattr(service, 'create_client_from_config', lambda _path: DummyMCPClient())
    try:
        with TestClient(service.app) as test_client:
            yield test_client
    finally:
        service.DB_PATH = old_db_path
        service._running_tasks.clear()
        service._running_tasks.update(old_tasks)
        service._mcp_client = old_mcp


@pytest.mark.asyncio
async def test_startup_creates_tasks_table_and_connects_mcp(monkeypatch, service_db_path: str):
    dummy = DummyMCPClient()
    monkeypatch.setattr(service, 'DB_PATH', service_db_path)
    monkeypatch.setattr(service, 'create_client_from_config', lambda _path: dummy)
    service._mcp_client = None

    await service.startup()

    conn = sqlite3.connect(service_db_path)
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='analysis_tasks'"
    ).fetchone()
    conn.close()

    assert row[0] == 'analysis_tasks'
    dummy.connect_all.assert_awaited_once()
    dummy.refresh_tools.assert_awaited_once()
    assert service._mcp_client is dummy

    await service.shutdown()


@pytest.mark.asyncio
async def test_startup_handles_mcp_initialization_failure(monkeypatch, service_db_path: str):
    monkeypatch.setattr(service, 'DB_PATH', service_db_path)
    monkeypatch.setattr(service, 'create_client_from_config', lambda _path: (_ for _ in ()).throw(RuntimeError('boom')))
    service._mcp_client = None

    await service.startup()

    assert service._mcp_client is None


@pytest.mark.asyncio
async def test_shutdown_closes_client_and_cancels_running_tasks():
    dummy = DummyMCPClient()
    task = asyncio.create_task(asyncio.sleep(10))
    service._mcp_client = dummy
    service._running_tasks.clear()
    service._running_tasks['trace-running'] = {'task': task, 'status': 'running'}

    await service.shutdown()
    await asyncio.sleep(0)

    dummy.close.assert_awaited_once()
    assert task.cancelled()
    assert service._mcp_client is None


def test_update_and_get_task_from_db_round_trip(monkeypatch, service_db_path: str):
    monkeypatch.setattr(service, 'DB_PATH', service_db_path)
    service._ensure_tasks_table(service_db_path)

    conn = sqlite3.connect(service_db_path)
    conn.execute(
        'INSERT INTO analysis_tasks (trace_id, status, alert_ids, started_at) VALUES (?, ?, ?, ?)',
        ('trace-db', 'started', json.dumps([1, 2]), '2026-03-08T10:00:00'),
    )
    conn.commit()
    conn.close()

    service._update_task_in_db('trace-db', status='completed', result=json.dumps({'risk_level': 'high'}), error=None)
    row = service._get_task_from_db('trace-db')

    assert row is not None
    assert row['status'] == 'completed'
    assert json.loads(row['result']) == {'risk_level': 'high'}
    assert row['completed_at'] is not None


def test_get_analysis_reads_persisted_task_when_not_in_memory(client, service_db_path: str):
    conn = sqlite3.connect(service_db_path)
    conn.execute(
        '''
        INSERT INTO analysis_tasks (trace_id, status, alert_ids, result, error, started_at, completed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ''',
        (
            'trace-persisted',
            'completed',
            json.dumps([7, 8]),
            json.dumps({'risk_level': 'medium', 'recommendation': 'monitor'}),
            None,
            '2026-03-08T10:00:00',
            '2026-03-08T10:02:00',
        ),
    )
    conn.commit()
    conn.close()

    response = client.get('/analyze/trace-persisted')

    assert response.status_code == 200
    body = response.json()
    assert body['status'] == 'completed'
    assert body['alert_ids'] == [7, 8]
    assert body['result']['recommendation'] == 'monitor'
    assert body['completed_at'] == '2026-03-08T10:02:00'


def test_get_analysis_returns_404_when_missing_everywhere(client):
    response = client.get('/analyze/not-found-trace')

    assert response.status_code == 404
    assert response.json()['detail'] == '未找到分析记录: not-found-trace'


def test_analyze_returns_500_when_alert_lookup_raises(monkeypatch, client):
    monkeypatch.setattr(service, '_fetch_alerts_by_ids', lambda _ids: (_ for _ in ()).throw(RuntimeError('db down')))

    response = client.post('/analyze', json={'alert_ids': [1]})

    assert response.status_code == 500
    assert response.json()['detail'] == '查询告警失败: db down'


def test_status_reports_no_active_tasks_without_mcp(client):
    service._mcp_client = None
    service._running_tasks.clear()
    service._running_tasks.update({
        'done': {'status': 'completed'},
        'failed': {'status': 'error'},
    })

    response = client.get('/status')

    assert response.status_code == 200
    body = response.json()
    assert body['mcp_connected'] is False
    assert body['mcp_servers'] == []
    assert body['running_tasks'] == 0


def test_approval_respond_rejects_invalid_status_payload(client):
    response = client.post('/approval/1/respond', json={'status': 'maybe'})

    assert response.status_code == 422


def test_chat_success_returns_content_and_usage(client):
    fake_response = MagicMock()
    fake_response.choices = [MagicMock(message=MagicMock(content='hello'))]
    fake_response.usage = MagicMock(prompt_tokens=12, completion_tokens=4)

    fake_client = MagicMock()
    fake_client.chat.completions.create = AsyncMock(return_value=fake_response)

    with patch('agent.service.AsyncOpenAI', return_value=fake_client):
        response = client.post('/chat', json={'messages': [{'role': 'user', 'content': 'hello'}], 'model': 'test-model'})

    assert response.status_code == 200
    body = response.json()
    assert body['content'] == 'hello'
    assert body['usage'] == {'prompt_tokens': 12, 'completion_tokens': 4}


def test_chat_maps_unhandled_exception_to_500(client):
    fake_client = MagicMock()
    fake_client.chat.completions.create = AsyncMock(side_effect=Exception('socket reset'))

    with patch('agent.service.AsyncOpenAI', return_value=fake_client):
        response = client.post('/chat', json={'messages': [{'role': 'user', 'content': 'hello'}], 'model': 'test-model'})

    assert response.status_code == 500
    assert response.json()['detail'] == '聊天请求失败: socket reset'
