from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from collector.clusterer import AlertClusterer


class FrozenDateTime(datetime):
    current = datetime(2025, 1, 1, tzinfo=timezone.utc)

    @classmethod
    def now(cls, tz=None):
        if tz is None:
            return cls.current.replace(tzinfo=None)
        return cls.current.astimezone(tz)


def make_alert(**overrides):
    base = {
        'source': 'waf',
        'title': 'Same Alert',
        'severity': 'medium',
        'src_ip': '10.0.0.1',
        'dst_ip': '192.168.1.1',
        'timestamp': '2025-01-01T00:00:00+00:00',
    }
    base.update(overrides)
    return base


def test_clusterer_flushes_expired_clusters_based_on_last_seen():
    clusterer = AlertClusterer(window_seconds=60)
    clusterer.add(make_alert())

    with patch('collector.clusterer.datetime', FrozenDateTime):
        FrozenDateTime.current = datetime(2025, 1, 1, 0, 2, 0, tzinfo=timezone.utc)
        expired = clusterer.flush_expired()

    assert len(expired) == 1
    assert expired[0].sample['title'] == 'Same Alert'
    assert clusterer.get_clusters() == []


def test_clusterer_flushes_old_cluster_when_window_is_exceeded():
    clusterer = AlertClusterer(window_seconds=300)
    clusterer.add(make_alert(timestamp='2025-01-01T00:00:00+00:00'))
    clusterer.add(make_alert(timestamp='2025-01-01T00:06:00+00:00'))

    with patch('collector.clusterer.datetime', FrozenDateTime):
        FrozenDateTime.current = datetime(2025, 1, 1, 0, 6, 10, tzinfo=timezone.utc)
        flushed = clusterer.flush_expired()

    active = clusterer.get_clusters()
    assert len(flushed) == 1
    assert flushed[0].count == 1
    assert len(active) == 1
    assert active[0].first_seen == '2025-01-01T00:06:00+00:00'


def test_clusterer_splits_same_title_when_ips_differ():
    clusterer = AlertClusterer(window_seconds=300)
    clusterer.add(make_alert(src_ip='10.0.0.1'))
    clusterer.add(make_alert(src_ip='10.0.0.2'))

    clusters = clusterer.get_clusters()
    assert len(clusters) == 2
    assert {tuple(c.source_ips) for c in clusters} == {('10.0.0.1',), ('10.0.0.2',)}
