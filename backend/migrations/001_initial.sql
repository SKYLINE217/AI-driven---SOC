-- =============================================================================
-- SOC Triager — Initial Database Schema
-- Runs automatically on Postgres container first boot via initdb.d
-- =============================================================================

-- Enable TimescaleDB
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- =============================================================================
-- 1. TIMESCALEDB HYPERTABLES (time-series data)
-- =============================================================================

-- Raw event store (append-only, 1-day chunks)
CREATE TABLE raw_events (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL,
    source_type TEXT NOT NULL,
    raw_payload JSONB NOT NULL
);
SELECT create_hypertable('raw_events', 'timestamp', chunk_time_interval => INTERVAL '1 day');

-- Normalized ECS events (1-day chunks)
CREATE TABLE normalized_events (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL,
    source_type TEXT NOT NULL,
    ecs_event JSONB NOT NULL,
    source_ip INET,
    destination_host TEXT,
    event_action TEXT,
    user_name TEXT
);
SELECT create_hypertable('normalized_events', 'timestamp', chunk_time_interval => INTERVAL '1 day');
CREATE INDEX ON normalized_events (source_ip, timestamp DESC);
CREATE INDEX ON normalized_events (destination_host, timestamp DESC);
CREATE INDEX ON normalized_events (event_action, timestamp DESC);

-- Feature snapshots for ML training (1-week chunks)
CREATE TABLE feature_snapshots (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    window_end TIMESTAMPTZ NOT NULL,
    entity_key TEXT NOT NULL,
    features JSONB NOT NULL
);
SELECT create_hypertable('feature_snapshots', 'window_end', chunk_time_interval => INTERVAL '1 week');
CREATE INDEX ON feature_snapshots (entity_key, window_end DESC);

-- =============================================================================
-- 2. ENTITY TRACKING
-- =============================================================================

CREATE TABLE entities (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    type TEXT NOT NULL CHECK (type IN ('host', 'user', 'ip')),
    value TEXT NOT NULL,
    first_seen TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata JSONB DEFAULT '{}',
    UNIQUE(type, value)
);

-- =============================================================================
-- 3. USER / AUTH
-- =============================================================================

CREATE TABLE users (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    role TEXT NOT NULL CHECK (role IN ('analyst', 'senior_analyst', 'approver')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Seed demo users
INSERT INTO users (email, role) VALUES
    ('analyst@example.com', 'analyst'),
    ('senior@example.com', 'senior_analyst'),
    ('approver@example.com', 'approver');

-- =============================================================================
-- 4. INCIDENTS & ALERTS
-- =============================================================================

CREATE TABLE incidents (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    title TEXT NOT NULL,
    severity TEXT NOT NULL CHECK (severity IN ('critical', 'high', 'medium', 'low', 'info')),
    status TEXT NOT NULL DEFAULT 'new' CHECK (status IN ('new', 'ack', 'escalated', 'closed')),
    technique_id TEXT NOT NULL,
    technique_name TEXT NOT NULL,
    tactic TEXT NOT NULL,
    confidence NUMERIC(4,3),
    llm_rationale TEXT,
    recommended_action TEXT,
    report_md TEXT,
    graph_mmd TEXT,
    playbook_draft TEXT,
    playbook_approved BOOLEAN DEFAULT FALSE,
    playbook_approved_by TEXT,
    playbook_approved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX ON incidents (status, severity, created_at DESC);
CREATE INDEX ON incidents (technique_id);

CREATE TABLE alerts (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    incident_id UUID REFERENCES incidents(id),
    severity TEXT NOT NULL CHECK (severity IN ('critical', 'high', 'medium', 'low', 'info')),
    timestamp TIMESTAMPTZ NOT NULL,
    source_ip INET,
    destination_host TEXT,
    user_name TEXT,
    technique_id TEXT NOT NULL,
    tactic TEXT NOT NULL,
    anomaly_score NUMERIC(4,3) NOT NULL,
    score_history NUMERIC(4,3)[] DEFAULT '{}',
    top_features JSONB,
    status TEXT NOT NULL DEFAULT 'new' CHECK (status IN ('new', 'ack', 'escalated', 'closed')),
    assignee TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX ON alerts (incident_id);
CREATE INDEX ON alerts (status, severity, created_at DESC);
CREATE INDEX ON alerts (source_ip, created_at DESC);
CREATE INDEX ON alerts (technique_id);

-- =============================================================================
-- 5. AUDIT LEDGER (append-only, hash-chained)
-- =============================================================================

CREATE TABLE incident_ledger (
    seq BIGSERIAL PRIMARY KEY,
    incident_id UUID NOT NULL REFERENCES incidents(id),
    hash TEXT NOT NULL UNIQUE,
    prev_hash TEXT NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    action TEXT NOT NULL,
    actor TEXT NOT NULL,
    payload JSONB NOT NULL
);
CREATE INDEX ON incident_ledger (incident_id, seq);

-- Row-level security: INSERT only, no UPDATE or DELETE
ALTER TABLE incident_ledger ENABLE ROW LEVEL SECURITY;
CREATE POLICY ledger_insert_only ON incident_ledger FOR INSERT WITH CHECK (true);
CREATE POLICY ledger_select_all ON incident_ledger FOR SELECT USING (true);

-- =============================================================================
-- 6. LLM CALL LOG (cost/latency tracking)
-- =============================================================================

CREATE TABLE llm_call_log (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    called_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    model TEXT NOT NULL,
    input_tokens INT NOT NULL,
    output_tokens INT NOT NULL,
    latency_ms INT NOT NULL,
    cluster_size INT NOT NULL,
    technique_result TEXT,
    cost_usd NUMERIC(10,6)
);
CREATE INDEX ON llm_call_log (called_at DESC);

-- =============================================================================
-- 7. CONTAINMENT TEMPLATES
-- =============================================================================

CREATE TABLE containment_templates (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    name TEXT NOT NULL,
    technique_category TEXT NOT NULL,
    template_source TEXT NOT NULL,
    ioc_variables TEXT[] NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Seed default templates
INSERT INTO containment_templates (name, technique_category, template_source, ioc_variables) VALUES
    ('Brute Force — IP Block + Account Lockout', 'T1110', '---
- name: Block attacker IP and lock targeted accounts
  hosts: edge-firewalls
  become: yes
  vars:
    attacker_ip: "{{ source_ip }}"
    target_accounts: "{{ target_users }}"
  tasks:
    - name: Block attacker IP at edge firewall
      iptables:
        chain: INPUT
        source: "{{ attacker_ip }}"
        jump: DROP
        comment: "SOC Triager — T1110 containment"

    - name: Lock targeted accounts
      user:
        name: "{{ item }}"
        password_lock: yes
      loop: "{{ target_accounts }}"
', ARRAY['source_ip', 'target_users']),

    ('Lateral Movement — Network Segmentation', 'T1021', '---
- name: Isolate compromised host via network ACL
  hosts: core-switches
  become: yes
  vars:
    pivot_host: "{{ pivot_host_ip }}"
    target_subnet: "{{ target_subnet }}"
  tasks:
    - name: Apply isolation ACL
      ios_config:
        lines:
          - "access-list 199 deny ip host {{ pivot_host }} {{ target_subnet }} 0.0.0.255"
          - "access-list 199 permit ip any any"
', ARRAY['pivot_host_ip', 'target_subnet']),

    ('DDoS Mitigation — Rate Limiting', 'T1498', '---
- name: DDoS mitigation — rate limit and null route
  hosts: edge-routers
  become: yes
  vars:
    source_cidrs: "{{ attacker_cidrs }}"
  tasks:
    - name: Apply rate limiting on attacker CIDRs
      iptables:
        chain: INPUT
        source: "{{ item }}"
        limit: "10/sec"
        limit_burst: 20
        jump: ACCEPT
        comment: "SOC Triager — T1498 rate limit"
      loop: "{{ source_cidrs }}"

    - name: Null route excessive traffic
      command: "ip route add blackhole {{ item }}"
      loop: "{{ source_cidrs }}"
', ARRAY['attacker_cidrs']),

    ('Privilege Escalation — Account Suspend', 'T1548', '---
- name: Suspend compromised account and kill sessions
  hosts: identity-servers
  become: yes
  vars:
    compromised_user: "{{ user_id }}"
    compromised_host: "{{ host }}"
  tasks:
    - name: Disable user account
      user:
        name: "{{ compromised_user }}"
        password_lock: yes

    - name: Kill all user sessions
      command: "pkill -u {{ compromised_user }}"
      ignore_errors: yes
', ARRAY['user_id', 'host']),

    ('Data Exfiltration — Egress Block', 'T1041', '---
- name: Block exfiltration egress path
  hosts: edge-firewalls
  become: yes
  vars:
    exfil_destination: "{{ destination_ip }}"
    exfil_port: "{{ port }}"
  tasks:
    - name: Block egress to exfiltration destination
      iptables:
        chain: OUTPUT
        destination: "{{ exfil_destination }}"
        destination_port: "{{ exfil_port }}"
        protocol: tcp
        jump: DROP
        comment: "SOC Triager — T1041 egress block"
', ARRAY['destination_ip', 'port']);

-- =============================================================================
-- Done — schema ready for SOC Triager backend
-- =============================================================================
