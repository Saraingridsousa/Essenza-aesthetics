# Integrated local demo and automation

The public GitHub Pages site remains entirely static. The Python/SQLite prototype serves the same landing page in a separate local-only integrated mode. It demonstrates durable synthetic lead ingestion and a transactional outbox. It never connects to the public GitHub Pages form, collects real client information, or sends notifications.

## Start the local API

Python 3.10+; no third-party dependencies. From the repository root, set `ESSENZA_DEMO_TOKEN` to a random secret of at least 24 characters. Generate one with `python -c "import secrets; print(secrets.token_urlsafe(32))"`. In PowerShell set it with `$env:ESSENZA_DEMO_TOKEN = 'your-generated-token'`; in bash use `export ESSENZA_DEMO_TOKEN='your-generated-token'`. Never commit the value.

Run `python -m backend.api`. The API binds to 127.0.0.1:8765 only. Open http://127.0.0.1:8765/ (not localhost), enter the token in the local banner, submit fictional sample data and open the dashboard. Status changes persist. Queue controls claim and acknowledge events or simulate a retryable failure; refresh to inspect the current counts. The public demo reset is disabled in integrated mode. Reloading requires reconnecting by token. The browser stores no token in persistent storage. SQLite file `essenza-demo.sqlite3` is ignored by Git. Stop the API and delete that file to reset.

The static UI, its logo and GET /health are public on loopback. Data endpoints require Authorization: Bearer <token>. POST /leads accepts JSON: {"name":"Teste Exemplo","email":"teste@example.com","service":"Limpeza de pele","consent":true}. Only reserved demo email domains and allowlisted service, period and origin values are accepted. Repeat the request to verify idempotent capture: HTTP 201 first, 200 with same ID thereafter. GET /leads and GET /metrics return data and current status counts. POST /leads/{id}/status accepts {"status":"Agendado"}.

## n8n demonstration

Import `automation/essenza-outbox.json` into a local n8n instance on the same host network. Create a Header Auth credential with name Authorization and value Bearer <token>; assign it to both HTTP Request nodes. If running n8n inside Docker, localhost points to the container; this loopback-only API is intentionally not exposed. Use a same-host native n8n instance rather than binding the API publicly.

Run the manual trigger after submitting a synthetic lead to the API. The workflow claims one event, simulates a notification without external side effects, and acknowledges the claim. No actual messages are sent. This workflow template has not been executed against a live n8n instance here. 

The API uses a transaction to create the lead and its event together; a uniqueness constraint avoids duplicates. Claims have a 120-second lease and unique lease token. Negative acknowledgements back off exponentially, with a maximum of five attempts. Expired leases can be reclaimed, and stale acknowledgements are rejected. Delivery semantics are at-least-once; a real receiver must deduplicate using the stable event ID. No names or emails are returned by the outbox endpoint.

## Tests

`python -m unittest backend.test_api -v` checks validation, idempotent capture, outbox creation, retries and lease fencing. `python -m unittest backend.test_browser -v` requires Playwright/Chromium and exercises the browser, HTTP API, SQLite persistence and queue simulation. These are functional tests, not a production security audit. Before any real deployment, implement user authentication, authorization, rate limits, HTTPS, encrypted storage, backups, audit/retention controls, monitoring, CRM delivery with deduplication and a clinical content review.

## Local worker and reporting

With the same ESSENZA_DB environment, run `python -m backend.worker process` to claim and acknowledge up to 20 available events, `python -m backend.worker fail` to simulate negative acknowledgements, and `python -m backend.worker report` to emit aggregate JSON. No notifications are sent. An operator may schedule the report locally, but no scheduler is configured.

## Optional local model

The public assistant is deterministic. For a native local demo, install and start Ollama separately, download a model you are authorized to use, and set ESSENZA_OLLAMA_MODEL to its installed model name before starting the backend. The backend connects only to 127.0.0.1:11434, sends approved sentences for an allowlisted topic, and validates the returned text against approved permutations. The raw visitor question and lead records never reach the model. If unavailable or invalid, the answer falls back to the knowledge base. This integration is unit-tested with a stub; a live Ollama inference run is not verified here. Do not use for medical advice.

## Docker

Set ESSENZA_DEMO_TOKEN in the shell and run `docker compose up --build` from the repository root. The API runs as a non-root user and port 8765 is mapped only to host loopback. SQLite is stored in a named volume. The optional Ollama and n8n examples are native-host setups; they are not included in this compose file. Do not expose this demo to the internet.
