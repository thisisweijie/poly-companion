# Poly Student Companion — Presenter Notes
*15 Jul 2026 · Lean cheat sheet · Keep open on second screen*

---

## What This Is

One app. Three microservices. Students open a single URL and see two features — Study Buddy and Makan Advisor. Everything runs on their laptop via Docker Compose.

```
Browser → localhost:7862
               ↓
         [ frontend ]          ← serves the UI, proxies requests
           /       \
 [study-buddy]  [makan-advisor]  ← pure REST APIs, no UI of their own
    :7860 (internal)  :7861 (internal)
```

Backends are not reachable from the browser directly — they only talk to the frontend over Docker's internal network. This mirrors how real production microservices are structured behind an API gateway.

---

## Why Three Containers and Not One

This is the core teaching point. One container per responsibility:

| Container | Job | Tech |
|---|---|---|
| `frontend` | Serves UI, proxies to backends, polls health | FastAPI + HTML/JS |
| `study-buddy` | Explains topics via LLM, streams response | FastAPI + HuggingFace |
| `makan-advisor` | Recommends hawker food via LLM, streams response | FastAPI + HuggingFace |

Neither backend knows the other exists. They share nothing — no code, no state, no network address. This is loose coupling made physical.

---

## The Files — One Line Each

```
poly-companion/
├── docker-compose.yml       orchestrates all 3; only frontend exposes a port
├── .env                     HF_TOKEN lives here, never in any code file
├── frontend/
│   ├── app.py               GET / → HTML page; GET /health → polls both backends;
│   │                        POST /ask + /recommend → stream proxy to backends
│   ├── requirements.txt     fastapi, uvicorn, httpx
│   └── Dockerfile           python:3.11-slim, port 7862
├── study-buddy/
│   ├── app.py               GET /health; POST /ask → StreamingResponse from LLM
│   ├── requirements.txt     fastapi, uvicorn, openai
│   └── Dockerfile           python:3.11-slim, port 7860
└── makan-advisor/
    ├── app.py               GET /health; POST /recommend → StreamingResponse from LLM
    ├── requirements.txt     fastapi, uvicorn, openai
    └── Dockerfile           python:3.11-slim, port 7861
```

### Key lines worth pointing out live

**`docker-compose.yml` — no ports on backends:**
```yaml
study-buddy:
  build: ./study-buddy
  # no 'ports:' — internal only
makan-advisor:
  build: ./makan-advisor
  # no 'ports:' — internal only
frontend:
  ports:
    - "7862:7862"   # only door into the system
```
> *"Students can only reach the frontend. The backends are completely sealed from the outside. The only way in is through the frontend — like a real API gateway."*

**`study-buddy/app.py` — streaming with `StreamingResponse`:**
```python
def generate():
    stream = client.chat.completions.create(..., stream=True)
    for chunk in stream:
        token = chunk.choices[0].delta.content or ""
        if token:
            yield token

return StreamingResponse(generate(), media_type="text/plain")
```
> *"The backend yields one token at a time. The frontend forwards each token to the browser the moment it arrives. That's the streaming chain — LLM → backend → frontend → browser — all in real time."*

**`frontend/app.py` — streaming proxy:**
```python
async with client.stream("POST", f"{STUDY_BUDDY_URL}/ask", json=...) as r:
    async for chunk in r.aiter_text():
        yield chunk
```
> *"The frontend doesn't wait for the full response. It reads chunks from the backend and forwards them immediately. Three services, one seamless stream."*

---

## The AI Angle — What to Say

> *"Both services call the same LLM — Gemma 4 (google/gemma-4-31b-it) on HuggingFace. But they each have a different system prompt, different inputs, different outputs, and a different job. Same infrastructure, completely different behaviour."*

> *"Watch the response build up word by word. This is streaming — the model sends tokens as it generates them, not all at once. This is the exact same pattern behind ChatGPT, Claude, Gemini. Our microservice does the same thing, scoped to one job."*

> *"Every AI feature you use daily — chatbots, recommendations, search ranking — is this pattern at scale. Thousands of these services. Each one independent. Orchestrated by Kubernetes."*

**Connection to slides:**
- Streaming = real production AI serving pattern → use this when transitioning from K8s slides to demo
- LLM as a microservice = connects your S14–15 Cloud Native AI slides back to the core content

---

## Demo Script

### Before touching the terminal

Show the folder structure first. Point at `docker-compose.yml`.

> *"One app. Three folders. Each folder is a microservice — its own code, its own Dockerfile, its own responsibility. The docker-compose.yml is the only thing that knows all three exist."*

Open `study-buddy/app.py`. Point at `/health` and `/ask`.

> *"Two endpoints. That's the entire public surface of this microservice. Health check so the frontend knows it's alive. Ask endpoint so the frontend can request an explanation."*

Show `makan-advisor/app.py`. Point out it's the same structure, different job.

> *"Same pattern. Different system prompt, different inputs, different outputs. Loose coupling — each service is only responsible for its own job."*  
> → **S26 — What are Microservices?** Each service has one job, one codebase, one team. No shared code, no shared state.  
> → **S29–32 — Why Microservices?** Flexibility (swap one without touching others), Reliability (one fails, others run), Scalability (scale only what's under load), Agility (teams ship independently).

---

### Step 1 — Start everything

```bash
cd path\to\poly-companion
docker-compose up --build
```

Point at the terminal output as it scrolls:

> *"See `study-buddy` and `makan-advisor` in the output? Two services building in parallel. Neither waits for the other."*

Wait for:
```
study-buddy   | Uvicorn running on http://0.0.0.0:7860
makan-advisor | Uvicorn running on http://0.0.0.0:7861
frontend      | Uvicorn running on http://0.0.0.0:7862
```

---

### Step 2 — Open the app

```
http://localhost:7862
```

Point at the two feature cards.

> *"One URL. Two features. This is what a microservices app looks like to the user — they have no idea there are three containers running underneath."*

Point at the architecture diagram at the bottom of the page.

> *"But we can see it. Three boxes, two connections, live status dots. The frontend is the only public-facing container — the backends are sealed off."*  
> → **S33–40 — Containers** Each service is packaged with its own code and dependencies — runs identically anywhere Docker runs. No "works on my machine."  
> → **S39–40 — Kubernetes / Orchestration** K8s does what docker-compose does here, but at scale — manages routing, restarts, and health across hundreds of containers.

---

### Step 3 — Demo Study Buddy

Click the Study Buddy card. Enter a topic — e.g. *"What is a microservice?"*, level Normal.

> *"Watch the response stream in token by token — just like ChatGPT. The backend is yielding tokens as fast as the LLM generates them."*

Try again with level Simple.

> *"Same service, same container, different system prompt — completely different explanation. The service adapts to the input, not to who calls it."*  
> → **S14–15 — Cloud Native AI** AI features are built and deployed as microservices, not bolted onto monoliths. The LLM here is just another service being called over an API.  
> → **AI payoff (hook slide callback)** Streaming token by token = the exact pattern behind ChatGPT, Claude, Gemini. Same infrastructure, scoped to one job.

---

### Step 4 — Demo Makan Advisor

Click Makan Advisor. Select Stressed / $4–$6 / No preference.

> *"Different inputs — dropdowns instead of a text box. Different output — a structured food card. Different job. But the same pattern underneath: one endpoint, one LLM call, one streaming response."*

> *"Study Buddy and Makan Advisor have never spoken to each other. They don't share any state or any code. This is what loose coupling looks like in practice."*

---

### Step 5 — THE KEY MOMENT — Stop Makan Advisor

Open a new terminal in the same folder.

```bash
docker-compose stop makan-advisor
```

Switch back to the browser. Point at the architecture diagram.

> *"Watch the Makan Advisor dot turn red. The frontend's health check picked it up within 3 seconds."*

Click the Makan Advisor card.

> *"Red error card: 'This service is currently down.' The frontend caught the failure and surfaced it cleanly."*

Click Study Buddy. Submit a question.

> *"Still working. Streaming. Didn't notice. One service is down — the other is completely unaffected."*

> *"In a monolith — what would have happened?"*  
> *(Pause. Let students answer.)*  
> *"Everything down. This is fault isolation."*  
> → **S30 — Reliability / Fault Isolation** A failure in one service stays contained. In a monolith, one bug can take down login, payment, everything. Here, Makan is down — Study Buddy never noticed.

---

### Step 6 — Restart

```bash
docker-compose start makan-advisor
```

> *"One command. Zero coordination with Study Buddy. The dot turns green. In Kubernetes, this restart would happen automatically — you wouldn't even run the command."*  
> → **K8s Deployment / Self-healing (new slides)** A Deployment tells K8s: "keep N copies of this service running." If a Pod crashes, K8s reconciles — desired state vs actual state — and spins a replacement up automatically.  
> → **S31–32 — Agility / Independent Deployment** The Makan team redeployed without a meeting, a sign-off, or touching Study Buddy. That's the agility microservices give you.

---

## Concept → Slide Reference

| Demo moment | Concept | Slide |
|---|---|---|
| Three separate folders/containers | Single Responsibility | S26 |
| Backends sealed, frontend as gateway | Loose coupling / independent deployment | S29–32 |
| `HF_TOKEN` from `.env`, never in code | 12-Factor Factor 3 (Config) | New 12-Factor slides |
| Streaming token by token | Real AI serving pattern | S14–15 + AI payoff |
| Terminal shows parallel builds | Independent services | S33–36 (Containers) |
| Architecture diagram with live dots | Observability / visibility | S39–40 (K8s) |
| Stopping makan-advisor, study-buddy runs | Fault isolation | S30 (Reliability) |
| `docker-compose start` with no coordination | Independent deployment | S31–32 (Agility) |

---

## Troubleshooting

| Problem | Fix |
|---|---|
| Port conflict | Change left port in `docker-compose.yml`, rerun `up --build` |
| HuggingFace 401 | Check `.env` — no spaces or quotes around token |
| Service won't build | Check terminal for error line under that service's prefix, rerun `up --build` |
| Browser won't load | Wait 15s after all three ready messages appear |
| Streaming appears all at once | Confirm `stream=True` in the API call and `yield token` in the generator |
| Fallback | Screen recording of all 6 steps — play and narrate over it if Docker fails |
