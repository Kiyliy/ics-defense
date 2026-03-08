import { describe, it, expect } from 'vitest';
import { normalize } from '../src/services/normalizer.js';

describe('normalizer', () => {
  it('normalize waf event maps severity, ips, and mitre fields', () => {
    const normalized = normalize('waf', {
      severity: '严重',
      rule_name: 'SQL injection attempt detected',
      reason: 'payload matched',
      src_ip: '10.0.0.8',
      dst_ip: '10.0.0.20',
    });

    expect(normalized).toEqual({
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

  it('normalize nids event uses nested alert payload and numeric severity', () => {
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

    expect(normalized.source).toBe('nids');
    expect(normalized.severity).toBe('high');
    expect(normalized.title).toBe('Brute force login');
    expect(normalized.description).toMatch(/SID:210001/);
    expect(normalized.src_ip).toBe('172.16.1.10');
    expect(normalized.dst_ip).toBe('172.16.1.20');
    expect(normalized.mitre_tactic).toBe('Initial Access');
    expect(normalized.mitre_technique).toBe('T0866');
  });

  it('normalize hids event falls back to agent ip and joins groups', () => {
    const normalized = normalize('hids', {
      agent: { ip: '192.168.50.15' },
      rule: {
        id: 5710,
        level: 5,
        description: 'Privilege escalation suspected',
        groups: ['syscheck', 'privilege'],
      },
    });

    expect(normalized.severity).toBe('critical');
    expect(normalized.src_ip).toBe('192.168.50.15');
    expect(normalized.dst_ip).toBe('192.168.50.15');
    expect(normalized.description).toBe('Rule:5710 Groups:syscheck,privilege');
    expect(normalized.mitre_tactic).toBe('Privilege Escalation');
    expect(normalized.mitre_technique).toBe('T0890');
  });

  it('normalize generic event returns unknown mitre mapping when no keyword matches', () => {
    const normalized = normalize('custom-source', {
      source: 'soc',
      title: 'Unusual telemetry spike',
      description: 'sensor deviation observed',
      severity: 'info',
      src_ip: '1.1.1.1',
      dst_ip: '2.2.2.2',
    });

    expect(normalized.source).toBe('soc');
    expect(normalized.severity).toBe('low');
    expect(normalized.mitre_tactic).toBe('Unknown');
    expect(normalized.mitre_technique).toBe(null);
  });
});
