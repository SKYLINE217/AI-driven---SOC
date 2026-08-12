# SOC Triager — HashiCorp Vault Policy
# Grants each Kubernetes service account read-only access to its own secret path.
# Applied via: vault policy write soc-incident-api infra/vault/policy.hcl

# ── Incident API ─────────────────────────────────────────────────────────────

path "secret/data/soc/incident-api/*" {
  capabilities = ["read"]
}

path "secret/data/soc/shared/*" {
  capabilities = ["read"]
}

# ── Scoring API ───────────────────────────────────────────────────────────────

path "secret/data/soc/scoring-api/*" {
  capabilities = ["read"]
}

path "secret/data/soc/shared/*" {
  capabilities = ["read"]
}

# ── Faust Worker ──────────────────────────────────────────────────────────────

path "secret/data/soc/faust-worker/*" {
  capabilities = ["read"]
}

path "secret/data/soc/shared/*" {
  capabilities = ["read"]
}

# ─────────────────────────────────────────────────────────────────────────────
# Secret paths (KV v2 layout)
#
# secret/data/soc/shared/
#   anthropic_api_key     — Anthropic API key (rotate monthly)
#   redis_url             — Redis connection string
#
# secret/data/soc/incident-api/
#   database_url          — PostgreSQL asyncpg DSN
#   jwt_private_key       — RS256 PEM private key (rotate quarterly)
#   jwt_public_key        — RS256 PEM public key
#
# secret/data/soc/scoring-api/
#   database_url          — PostgreSQL DSN (same or dedicated schema)
#   mlflow_tracking_uri   — MLflow server URI
#
# secret/data/soc/faust-worker/
#   database_url          — PostgreSQL DSN
#   kafka_bootstrap_servers — Redpanda brokers
# ─────────────────────────────────────────────────────────────────────────────
