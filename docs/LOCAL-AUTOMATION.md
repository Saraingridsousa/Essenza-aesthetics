# Local automation prototype (V3)

The public GitHub Pages site remains entirely static. This separate Python/SQLite prototype demonstrates durable synthetic lead ingestion and a transactional outbox. It does not connect to the public form, collect real client information, or send notifications.

## Start the local API

Python 3.10+; no third-party dependencies. From the repository root, set `ESSENZA_DEMO_TOKEN` to a random secret of at least 24 characters. Generate one with `python -c "import secrets; print(secrets.token_urlsafe(32))"`. In PowerShell set it with `$env:ESSENZA_DEMO_TOKEN = 'your-generated-token'`; in bash use `export ESSENZA_DEMO_TOKEN='your-generated-token'`. Never commit the value.

Run `python -m backend.api`. The API binds to 127.0.0.1:8765 only. SQLite file `essenza-demo.sqlite3` is ignored by Git. Stop the API and delete that file to reset.

All endpoints except GET /health require Authorization: Bearer <token>. POST /leads accepts JSON: {"name":"Teste Exemplo","email":"teste@example.com","service":"Limpeza de pele","consent":true}. Only reserved demo email domains and allowlisted service, period and origin values are accepted. Repeat the request to verify idempotent capture: HTTP 201 first, 200 with same ID thereafter. GET /leads and GET /metrics return data and current status counts. POST /leads/{id}/status accepts {"status":"Agendado"}.

## n8n demonstration

Import `automation/essenza-outbox.json` into a local n8n instance on the same host network. Create a Header Auth credential with name Authorization and value Bearer <token>; assign it to both HTTP Request nodes. If running n8n inside Docker, localhost points to the container; this loopback-only API is intentionally not exposed. Use a same-host native n8n instance rather than binding the API publicly.

Run the manual trigger after submitting a synthetic lead to the API. The workflow claims one event, simulates a notification without external side effects, and acknowledges the claim. No actual messages are sent. This workflow template has not been executed against a live n8n instance here. 

The API uses a transaction to create the lead and its event together; a uniqueness constraint avoids duplicates. Claims have a 120-second lease and unique lease token. Negative acknowledgements back off exponentially, with a maximum of five attempts. Expired leases can be reclaimed, and stale acknowledgements are rejected. Delivery semantics are at-least-once; a real receiver must deduplicate using the stable event ID. No names or emails are returned by the outbox endpoint.

## Tests

`python -m unittest backend.test_api -v` checks validation, idempotent capture, outbox creation, retries and lease fencing. These are domain tests, not a production security audit. Before any real deployment, implement user authentication, authorization, rate limits, HTTPS, encrypted storage, backups, audit/retention controls, monitoring, CRM delivery with deduplication and a clinical content review.

The browser FAQ is deterministic, not an LLM. A future generative assistant would require a curated knowledge base, evaluation and escalation rules; it must not recommend clinical procedures or diagnose.
