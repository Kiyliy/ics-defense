from __future__ import annotations

import sqlite3
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from agent.audit import AuditLogger
from agent import service


SCHEMA_SQL = Path('tests/conftest.py').read_text(encoding='utf-8').split('SCHEMA_SQL = """', 1)[1].split('"""', 1)[0]


@pytest.fixture
def service_db_path(tmp_path: Path) -> str:
    db_path = str(tmp_path / 'service-test.db')
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    conn.close()
    return db_path


@pytest.fixture
def client(service_db_path: str):
    old_db_path = service.DB_PATH
    old_tasks = dict(service._running_tasks)
    old_mcp = service._mcp_client
    service.DB_PATH = service_db_path
    service._running_tasks.clear()
    service._mcp_client = None
    try:
        with TestClient(service.app) as test_client:
            yield test_client
    finally:
        service.DB_PATH = old_db_path
        service._running_tasks.clear()
        service._running_tasks.update(old_tasks)
        service._mcp_client = old_mcp


def test_make_clustered_alerts_uses_source_and_ips_in_signature():
    alerts = [
        {'title': 'SQL注入', 'source': 'waf', 'severity': 'high', 'src_ip': '10.0.0.1', 'dst_ip': '192.168.0.10', 'created_at': '2026-03-08T10:00:00Z'},
        {'title': 'SQL注入', 'source': 'waf', 'severity': 'high', 'src_ip': '10.0.0.1', 'dst_ip': '192.168.0.10', 'created_at': '2026-03-08T10:01:00Z'},
        {'title': 'SQL注入', 'source': 'waf', 'severity': 'high', 'src_ip': '10.0.0.9', 'dst_ip': '192.168.0.10', 'created_at': '2026-03-08T10:02:00Z'},
        {'title': '端口扫描', 'source': 'nids', 'severity': 'medium', 'src_ip': '10.0.0.2', 'dst_ip': '192.168.0.11', 'created_at': '2026-03-08T10:03:00Z'},
    ]

    clusters = service._make_clustered_alerts(alerts)

    assert len(clusters) == 3
    sql_cluster = next(cluster for cluster in clusters if cluster['signature'] == 'SQL注入|waf|10.0.0.1|192.168.0.10')
    assert sql_cluster['count'] == 2
    assert sql_cluster['first_seen'] == '2026-03-08T10:00:00Z'
    assert sql_cluster['last_seen'] == '2026-03-08T10:01:00Z'
    assert sql_cluster['source_ips'] == ['10.0.0.1']
    assert sql_cluster['target_ips'] == ['192.168.0.10']


def test_get_analysis_recovers_completed_result_from_audit_logs(client, service_db_path: str):
    audit = AuditLogger(service_db_path)
    trace_id = 'trace-from-audit'
    decision = {'risk_level': 'high', 'recommendation': 'block', 'action_type': 'block'}
    audit.log(trace_id, 'decision_made', decision, token_usage={'input_tokens': 3, 'output_tokens': 2})
    audit.log(trace_id, 'analysis_finished', {'risk_level': 'high'})
    audit.close()

    response = client.get(f'/analyze/{trace_id}')

    assert response.status_code == 200
    body = response.json()
    assert body['status'] == 'completed'
    assert body['result']['risk_level'] == 'high'
    assert body['token_usage']['total'] == 5
    assert len(body['audit_logs']) == 2


def test_status_counts_only_started_and_running_tasks(client):
    mock_mcp = MagicMock()
    mock_mcp.get_connected_servers.return_value = ['log-search', 'memory']
    service._mcp_client = mock_mcp
    service._running_tasks.update({
        'a': {'status': 'started'},
        'b': {'status': 'running'},
        'c': {'status': 'completed'},
        'd': {'status': 'error'},
    })

    response = client.get('/status')

    assert response.status_code == 200
    body = response.json()
    assert body['mcp_connected'] is True
    assert body['mcp_servers'] == ['log-search', 'memory']
    assert body['running_tasks'] == 2


def test_approval_respond_updates_pending_record(client, service_db_path: str):
    conn = sqlite3.connect(service_db_path)
    conn.execute(
        "INSERT INTO approval_queue (trace_id, tool_name, tool_args, reason, status) VALUES (?, ?, ?, ?, ?)",
        ('trace-1', 'block_ip', '{}', 'need approval', 'pending'),
    )
    conn.commit()
    conn.close()

    response = client.post('/approval/1/respond', json={'status': 'approved', 'reason': 'looks good'})

    assert response.status_code == 200
    assert response.json()['status'] == 'approved'

    conn = sqlite3.connect(service_db_path)
    status = conn.execute('SELECT status FROM approval_queue WHERE id = 1').fetchone()[0]
    conn.close()
    assert status == 'approved'


def test_chat_maps_auth_error_to_401(client):
    with patch('agent.service.OpenAI') as MockOpenAI:
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception('401 unauthorized')
        MockOpenAI.return_value = mock_client

        response = client.post('/chat', json={'messages': [{'role': 'user', 'content': 'hello'}], 'model': 'test-model'})

    assert response.status_code == 401
    assert response.json()['detail'] == 'API Key 无效'
