import test from 'node:test';
import assert from 'node:assert/strict';
import { normalize } from '../src/services/normalizer.js';

test('normalize waf event maps severity, ips, and mitre fields', () => {
  const normalized = normalize('waf', {
    severity: '严重',
    rule_name: 'SQL injection attempt detected',
    reason: 'payload matched',
    src_ip: '10.0.0.8',
    dst_ip: '10.0.0.20',
  });

  assert.deepEqual(normalized, {
    source: 'waf',
    severity: 'critical',
    title: 'SQL injection attempt detected',
    description: 'payload matched',
    src_ip: '10.0.0.8',
    dst_ip: '10.0.0.20',
    mitre_tactic: 'Execution',
    mitre_technique: 'T0807',
  });
});

test('normalize nids event uses nested alert payload and numeric severity', () => {
  const normalized = normalize('nids', {
    src_ip: '172.16.1.10',
    dest_ip: '172.16.1.20',
    alert: {
      severity: 3,
      signature: 'Brute force login',
      signature_id: 210001,
      category: 'Attempted Administrator Privilege Gain',
    },
  });

  assert.equal(normalized.source, 'nids');
  assert.equal(normalized.severity, 'high');
  assert.equal(normalized.title, 'Brute force login');
  assert.match(normalized.description, /SID:210001/);
  assert.equal(normalized.src_ip, '172.16.1.10');
  assert.equal(normalized.dst_ip, '172.16.1.20');
  assert.equal(normalized.mitre_tactic, 'Initial Access');
  assert.equal(normalized.mitre_technique, 'T0866');
});

test('normalize hids event falls back to agent ip and joins groups', () => {
  const normalized = normalize('hids', {
    agent: { ip: '192.168.50.15' },
    rule: {
      id: 5710,
      level: 5,
      description: 'Privilege escalation suspected',
      groups: ['syscheck', 'privilege'],
    },
  });

  assert.equal(normalized.severity, 'critical');
  assert.equal(normalized.src_ip, '192.168.50.15');
  assert.equal(normalized.dst_ip, '192.168.50.15');
  assert.equal(normalized.description, 'Rule:5710 Groups:syscheck,privilege');
  assert.equal(normalized.mitre_tactic, 'Privilege Escalation');
  assert.equal(normalized.mitre_technique, 'T0890');
});

test('normalize generic event returns unknown mitre mapping when no keyword matches', () => {
  const normalized = normalize('custom-source', {
    source: 'soc',
    title: 'Unusual telemetry spike',
    description: 'sensor deviation observed',
    severity: 'info',
    src_ip: '1.1.1.1',
    dst_ip: '2.2.2.2',
  });

  assert.equal(normalized.source, 'soc');
  assert.equal(normalized.severity, 'low');
  assert.equal(normalized.mitre_tactic, 'Unknown');
  assert.equal(normalized.mitre_technique, null);
});
