from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml

from agent.hooks import HookManager


@pytest.fixture
def minimal_hooks_yaml(tmp_path: Path) -> str:
    path = tmp_path / 'hooks.yaml'
    path.write_text(yaml.dump({'hooks': {}}, allow_unicode=True), encoding='utf-8')
    return str(path)


@pytest.mark.asyncio
async def test_send_webhook_skips_empty_url_and_does_not_call_http(minimal_hooks_yaml: str):
    manager = HookManager(config_path=minimal_hooks_yaml)

    with patch('agent.hooks.httpx.AsyncClient') as MockClient:
        await manager._action_send_webhook({'url': ''}, {'severity': 'high'})

    MockClient.assert_not_called()


@pytest.mark.asyncio
async def test_send_webhook_builds_feishu_payload_and_resolves_env_var(minimal_hooks_yaml: str, monkeypatch):
    manager = HookManager(config_path=minimal_hooks_yaml)
    monkeypatch.setenv('HOOK_URL', 'https://open.feishu.cn/webhook/abc')

    response = MagicMock()
    response.status_code = 200
    response.raise_for_status.return_value = None
    client = AsyncMock()
    client.post.return_value = response
    client.__aenter__.return_value = client
    client.__aexit__.return_value = None

    with patch('agent.hooks.httpx.AsyncClient', return_value=client):
        await manager._action_send_webhook({'url': '${HOOK_URL}'}, {'title': '告警', 'severity': 'critical'})

    call = client.post.call_args
    assert call.args[0] == 'https://open.feishu.cn/webhook/abc'
    payload = call.kwargs['json']
    assert payload['msg_type'] == 'interactive'
    assert payload['card']['header']['template'] == 'red'
    assert payload['card']['header']['title']['content'] == '告警'


@pytest.mark.asyncio
async def test_send_webhook_uses_generic_payload_for_non_feishu_url(minimal_hooks_yaml: str):
    manager = HookManager(config_path=minimal_hooks_yaml)

    response = MagicMock()
    response.status_code = 204
    response.raise_for_status.return_value = None
    client = AsyncMock()
    client.post.return_value = response
    client.__aenter__.return_value = client
    client.__aexit__.return_value = None

    with patch('agent.hooks.httpx.AsyncClient', return_value=client):
        await manager._action_send_webhook({'url': 'https://example.com/hook'}, {'event': 'decision'})

    payload = client.post.call_args.kwargs['json']
    assert payload == {'event': 'hook_notification', 'context': {'event': 'decision'}}


@pytest.mark.asyncio
async def test_push_websocket_logs_and_swallows_http_failure(minimal_hooks_yaml: str):
    manager = HookManager(config_path=minimal_hooks_yaml)

    client = AsyncMock()
    client.post.side_effect = RuntimeError('network down')
    client.__aenter__.return_value = client
    client.__aexit__.return_value = None

    with patch('agent.hooks.httpx.AsyncClient', return_value=client):
        await manager._action_push_websocket({'channel': 'secops'}, {'event': 'analysis_started'})

    client.post.assert_awaited_once()
