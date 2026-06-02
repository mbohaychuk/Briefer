# Using Briefer

## What this is
Briefer is a personalized news intelligence stack: an ASP.NET Core web-api for
auth/profiles/orchestration, a Python FastAPI ml-service for ingestion +
embedding + LLM scoring, Postgres for relational data, Qdrant for vector
search, and Ollama for local LLM inference. Bring it up with Docker Compose
and it ingests RSS feeds, embeds articles, and (eventually) scores them
against your declared interests.

## Prerequisites
- Docker + Docker Compose
- A running `ollama-portfolio` container exposing host port `11434` and
  attached to the `briefer_default` Docker network (so the ml-service can
  reach `http://ollama-portfolio:11434`)
- Models pulled inside that container: `llama3.2:3b` and `nomic-embed-text`
- ~6 GB free RAM (web-api + ml-service torch deps are heavy)
- Host port `5432` free (else use the local override below to rebind/hide it)

## First-time setup
1. Confirm `.env` exists at repo root. Required overrides for the
   portfolio-demo Ollama setup (these are already in the committed `.env`):
   ```
   LLM_PROVIDER=ollama
   OLLAMA_BASE_URL=http://ollama-portfolio:11434
   OLLAMA_MODEL=llama3.2:3b
   OLLAMA_TIMEOUT=180
   ```
   The ml-service default of `gemma4` is not a real Ollama tag — see Known
   issues.
2. Start the Ollama container and confirm models:
   ```
   docker start ollama-portfolio
   docker exec ollama-portfolio ollama list
   # expect llama3.2:3b and nomic-embed-text:latest
   ```
3. `docker-compose.local.yml` (gitignored) holds dev overrides: drops the
   postgres host-port binding, fixes Qdrant's broken healthcheck, and
   exposes ml-service on `:8000` so you can hit it directly.

## Run it
From the repo root:
```
docker compose -f docker-compose.yml -f docker-compose.local.yml up -d
docker ps --filter name=briefer
```
You should see all four containers `Up`, with `briefer-postgres-1` and
`briefer-qdrant-1` reporting `(healthy)`. Web-api listens on host `:5000`,
ml-service on host `:8000`.

Verify:
```
curl -s http://localhost:8000/health
# {"status":"healthy","database":"connected","qdrant":"connected"}

curl -s -o /dev/null -w "%{http_code}\n" http://localhost:6333/healthz  # 200
```
Web-api has no `/health` endpoint — confirm it's up by hitting an actual
route (see below). EF migrations run on startup; on a fresh DB the first
boot adds ~5 s.

## Try it out
All examples assume the demo `.env`. Replace credentials for real use.

1. Register and grab a JWT:
   ```
   TOKEN=$(curl -s -X POST http://localhost:5000/api/auth/register \
     -H "Content-Type: application/json" \
     -d '{"email":"demo@briefer.local","password":"DemoPass123!"}' \
     | jq -r .token)
   ```
2. Add an interest to your profile:
   ```
   curl -s -X POST http://localhost:5000/api/profile/interests \
     -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
     -d '{"title":"AI safety","description":"Frontier AI safety research, alignment, and governance."}'

   curl -s http://localhost:5000/api/profile -H "Authorization: Bearer $TOKEN"
   # {"version":2,"interests":[{"id":"...","title":"AI safety",...}]}
   ```
3. Trigger an ingest *directly against ml-service* (see Polly gotcha below):
   ```
   curl -X POST http://localhost:8000/api/ingestion/trigger \
     -H "X-Api-Key: changeme_dev_ml_api_key"
   ```
   Fetching ~30 RSS feeds + extracting full text + embedding takes several
   minutes; the endpoint blocks until done. Check progress in a second
   terminal:
   ```
   docker logs -f briefer-ml-service-1
   docker exec briefer-postgres-1 psql -U newssearcher -d newssearcher \
     -c "SELECT COUNT(*) FROM articles;"
   ```

## Known issues / gotchas
- **CORS missing in web-api.** No CORS policy is registered, so a browser
  frontend served from any other origin gets blocked at preflight. Manual
  workaround for poking the UI:
  `chromium --disable-web-security --user-data-dir=/tmp/cdw`.
  Proper fix is a CORS policy in `NewsSearcher.Api`.
- **30 s Polly timeout on web-api → ml-service calls.** Long ml-service
  jobs (ingestion, scoring) finish well past 30 s, so the web-api wrapper
  returns HTTP 500 even when the underlying call succeeds. Workaround: call
  `http://localhost:8000/api/...` directly with
  `X-Api-Key: changeme_dev_ml_api_key`. The DB and Qdrant still reflect the
  completed work.
- **Default `OLLAMA_MODEL=gemma4` is invalid.** `gemma4` is not an Ollama
  tag. The committed `.env` overrides it to `llama3.2:3b`; if you start
  from a clean env, set `OLLAMA_MODEL=llama3.2:3b` (or another pulled tag)
  before `docker compose up` or LLM scoring will 404.
- **LLM scoring is slow on CPU.** A full briefing pipeline (ingest → score
  every new article with `llama3.2:3b` → assemble) takes 20+ minutes per
  run on a CPU-only host. Trigger it and walk away; don't poll tightly.
- **Postgres binds host `:5432` in the base compose.** If something else
  on the host already owns 5432 (a system postgres, another project), the
  included `docker-compose.local.yml` resets the host-port binding so the
  DB is reachable only from inside the Docker network. To expose it on the
  host instead, rebind to `5435:5432` in your local override.

## Stop / cleanup
Stop the stack but keep data:
```
docker compose -f docker-compose.yml -f docker-compose.local.yml stop
docker stop ollama-portfolio
```
Wipe everything including the article corpus and user table:
```
docker compose -f docker-compose.yml -f docker-compose.local.yml down -v
```
The `postgres_data` and `qdrant_data` named volumes hold all ingest state;
removing them costs you the 5k+ articles already embedded.
