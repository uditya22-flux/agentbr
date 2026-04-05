-- ============================================================
-- AgentBridge v6 — B2B SaaS Multi-tenant Schema
-- ============================================================

-- 1. Organizations (Tenants)
CREATE TABLE IF NOT EXISTS organizations (
    id          UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    name        TEXT NOT NULL,
    industry    TEXT, -- fintech | bank | NBFC | other
    plan        TEXT DEFAULT 'free', -- free | starter | pro
    api_limit   INT DEFAULT 1000
);

-- 2. Users (Company Admins/Viewers)
CREATE TABLE IF NOT EXISTS users (
    id            UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    org_id        UUID REFERENCES organizations(id) ON DELETE CASCADE,
    email         TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    full_name     TEXT,
    role          TEXT DEFAULT 'admin' -- admin | viewer
);

-- 3. Agents
CREATE TABLE IF NOT EXISTS agents (
    id            UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    org_id        UUID REFERENCES organizations(id) ON DELETE CASCADE,
    name          TEXT NOT NULL,
    agent_type    TEXT NOT NULL, -- fraud-detection | loan-approval | KYC | other
    description   TEXT,
    api_key_hash  TEXT NOT NULL UNIQUE,
    status        TEXT DEFAULT 'active', -- active | inactive
    total_logs    INT DEFAULT 0
);

-- 4. Audit Logs (Immutable)
CREATE TABLE IF NOT EXISTS audit_logs (
    id                    UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    created_at            TIMESTAMPTZ DEFAULT NOW(),
    org_id                UUID REFERENCES organizations(id) ON DELETE CASCADE,
    agent_id              UUID REFERENCES agents(id) ON DELETE CASCADE,
    
    -- Identity & Context
    decision_id           TEXT NOT NULL,
    session_id            TEXT,
    user_id               TEXT,
    action_type           TEXT,
    domain                TEXT DEFAULT 'fintech',

    -- Gateway Verdict
    verdict               TEXT NOT NULL,   -- allow | review | reject
    risk_score            FLOAT,
    risk_level            TEXT,
    flagged               BOOLEAN DEFAULT FALSE,

    -- Policy & Compliance
    policy_violations     JSONB DEFAULT '[]',
    compliance_violations JSONB DEFAULT '[]',
    compliance_tags       JSONB DEFAULT '[]',

    -- Agent Data
    inputs                JSONB,           -- Changed to JSONB for better storage/querying
    output                TEXT,
    reasoning             TEXT,
    confidence            FLOAT,
    latency_ms            INT,
    status                TEXT,

    -- AI analysis
    ai_explanation        TEXT,
    ai_recommended_action TEXT,
    ai_compliance_status  TEXT,
    ai_risk_level         TEXT,
    ai_category           TEXT,
    ai_issue_detected     BOOLEAN,
    ai_confidence_score   FLOAT,
    ai_escalate_to_human  BOOLEAN DEFAULT FALSE,
    ai_regulatory_refs    JSONB DEFAULT '[]',

    -- Security
    previous_hash         TEXT,            -- Optional for now, but good for immutability logic
    log_hash              TEXT UNIQUE
);

-- 5. Incidents (Flagged violations for review)
CREATE TABLE IF NOT EXISTS incidents (
    id            UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    org_id        UUID REFERENCES organizations(id) ON DELETE CASCADE,
    log_id        UUID REFERENCES audit_logs(id) ON DELETE CASCADE,
    agent_id      UUID REFERENCES agents(id) ON DELETE CASCADE,
    severity      TEXT NOT NULL, -- high | medium | low
    status        TEXT DEFAULT 'open', -- open | reviewing | resolved
    rule_triggered TEXT,
    resolved_at   TIMESTAMPTZ,
    resolved_by   UUID REFERENCES users(id),
    resolution_note TEXT
);

-- 6. Compliance Reports (Historical snapshots)
CREATE TABLE IF NOT EXISTS compliance_reports (
    id            UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    org_id        UUID REFERENCES organizations(id) ON DELETE CASCADE,
    agent_id      UUID REFERENCES agents(id) ON DELETE CASCADE, -- Optional (can be org-wide)
    score         INT,
    clauses_passed INT,
    clauses_failed INT,
    report_data   JSONB,
    exported_as   TEXT -- pdf | csv
);

-- 7. Audit Trail (Internal Platform Logs)
CREATE TABLE IF NOT EXISTS platform_audit_logs (
    id            UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    org_id        UUID REFERENCES organizations(id),
    user_id       UUID REFERENCES users(id),
    action        TEXT NOT NULL, -- login | key_revoke | agent_create | report_export
    metadata      JSONB
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_audit_logs_org_id ON audit_logs(org_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_agent_id ON audit_logs(agent_id);
CREATE INDEX IF NOT EXISTS idx_users_org_id ON users(org_id);
CREATE INDEX IF NOT EXISTS idx_agents_org_id ON agents(org_id);
CREATE INDEX IF NOT EXISTS idx_incidents_org_id ON incidents(org_id);
CREATE INDEX IF NOT EXISTS idx_incidents_status ON incidents(status);
