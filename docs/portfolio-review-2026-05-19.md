# Portfolio review notes — 2026-05-19

Notes collected while preparing this project for portfolio capture.

Severity legend:
- 🔴 **Blocker** — would prevent a recruiter from running or evaluating the project
- 🟠 **Embarrassing** — visible to anyone who clones the repo; should be fixed before sharing
- 🟡 **Polish** — minor UX, docs, or code quality
- 🟢 **Idea** — not a defect; potential improvement to discuss

## 🔴 Blockers

### 1. The web-api has no CORS policy — the frontend cannot talk to it in a browser
`src/web-api/Briefer.Api/Program.cs` never calls `AddCors` / `UseCors`. The Nuxt frontend (`src/frontend/nuxt.config.ts`) calls `http://localhost:5000/api` directly from the browser. Because the frontend runs on `localhost:3000` and the API on `localhost:5000`, every request is cross-origin — and the browser blocks it at the preflight stage:

```
Access to fetch at 'http://localhost:5000/api/auth/register' from origin
'http://localhost:3000' has been blocked by CORS policy: No
'Access-Control-Allow-Origin' header is present on the requested resource.
```

As shipped, the full product does not work in a browser. Registration, login, the dashboard — all fail. The fix is ~4 lines in `Program.cs` (`builder.Services.AddCors(...)` with a policy allowing the frontend origin, then `app.UseCors(...)`), or a Nitro dev proxy in `nuxt.config.ts` so the two share an origin. This portfolio capture had to launch the browser with `--disable-web-security` to get the UI to function. **This is the single most important thing to fix** — a recruiter who clones the repo and follows the README will hit a blank, broken dashboard.

### 2. Default LLM model `gemma4` is not a real Ollama model
`src/ml-service/app/config.py:30` — `self.ollama_model = os.environ.get("OLLAMA_MODEL", "gemma4")`. Ollama publishes `gemma`, `gemma2`, `gemma3` — there is no `gemma4`. A clone-and-run user with the default config gets an immediate model-not-found error from Ollama. Either this is a typo for `gemma3`, or it refers to a model that must be `ollama create`-d locally and that process isn't documented. The portfolio capture overrode this to `llama3.2:3b` via `.env`.

## 🟠 Embarrassing

### 3. Ollama is a hard runtime dependency but is absent from docker-compose and undocumented
`docker-compose.yml` defines postgres, qdrant, web-api, ml-service — no Ollama, and no comment that it is required. `ml-service` defaults `OLLAMA_BASE_URL` to `http://localhost:11434`, which from inside the container resolves to the container itself, not the host. A reader of the compose file has no way to know an LLM runtime must exist, where, or how ml-service should reach it. Add an `ollama` service to the compose file (or document the external requirement prominently in the README and `.env.example`).

### 4. The per-user interest profile and the scoring profile are two disconnected systems
The web-api stores per-user interest blocks in Postgres (managed via `ProfileController`, editable in the frontend's `/profile` page). But `src/ml-service/app/main.py:72` loads the scoring persona from a flat file — `profile_loader.load_from_file(settings.profiles_path)` (`profiles.json`). The scoring pipeline ranks articles against `profiles.json`, **not** against whatever the logged-in user typed into the profile editor. The `set_profile_loader` / sync wiring at `main.py:76` exists in skeleton form, but the web-api never pushes profile updates to ml-service. Net effect: editing your interests in the UI has no effect on your briefing. This is the most significant half-finished feature — and it is not obvious from the outside, which makes it worse.

### 5. 60-second HTTP timeout on the ml-service client will fire during real scoring
`src/web-api/Briefer.Api/Program.cs:51` — `client.Timeout = TimeSpan.FromSeconds(60)`. Scoring a batch through the LLM cascade against a local Ollama model routinely takes minutes (the LLM calls serialize). When this 60s timeout trips, the frontend surfaces a scoring error even though ml-service finishes the work successfully a few minutes later. The timeout should be sized to the realistic worst-case scoring duration, or the scoring call should be made asynchronous (fire-and-poll) rather than a single long request.

## 🟡 Polish

### 6. Bare `except Exception` swallows RSS feed failures silently
`src/ml-service/app/ingestion/plugins/rss_plugin.py:53` — `except Exception:` catches everything with only a warning log. A feed that 403s, redirects to HTML, or changes format silently contributes zero articles; the ingestion result just shows a lower count with no indication which feed failed or why. Catch specific exceptions, or at minimum include the feed URL and error in the surfaced result so a degraded feed is visible.

### 7. `docker-compose.local.yml` publicly documents a worked-around bug
`docker-compose.local.yml:7` — the comment "Upstream image lacks curl; the committed healthcheck never passes." This is honest, but it advertises to anyone reading the repo that the committed `docker-compose.yml` healthcheck is broken and was patched over rather than fixed. Better: fix the healthcheck in the base `docker-compose.yml` (the local override already shows the working `/dev/tcp` form) and delete the apologetic comment.

## 🟢 Ideas

### 8. The cascade-miss logging is genuinely strong — make sure the README sells it
The design choice of sending 12 cross-encoder-rejected articles to the LLM anyway, to detect cascade misses, is the most interesting engineering decision in the project. It already reads well on the portfolio page. Make sure the repo README gives it equal prominence — it is the thing that signals real ML-systems thinking.

### 9. Consider standardizing the default branch to `main`
This repo's default branch is `master`; your other three project repos use `main`. Minor, but across a candidate's repo set the inconsistency is visible on GitHub.
