# Poly Student Companion — Presenter Notes
*15 Jul 2026 · Lean cheat sheet · Keep open on second screen*

---

## Tech Stack — What, Why, and Why Not

| Technology | Role in this demo | Why this | Why not X |
|---|---|---|---|
| **FastAPI** | REST API framework for all 3 services | Async-native, fast to write, auto-generates `/docs` — good for showing clean API contracts | Flask has no native async (matters for streaming); Django is too heavy; Gradio locks UI to the backend which defeats the microservices point |
| **Uvicorn** | ASGI server that runs FastAPI | Lightweight, production-grade, handles async and streaming cleanly | Gunicorn alone doesn't support async; Flask's dev server is not production-appropriate |
| **Docker** | Packages each service into its own container | Guarantees identical behaviour on any machine — no "works on my machine" | Bare Python scripts have no isolation; each student's machine would have different environments and break differently |
| **Docker Compose** | Starts all 3 containers with one command | Simple enough for a demo, shows orchestration concept clearly, maps directly to Lab 5 content | Kubernetes is the real-world equivalent but too complex to install locally for a live demo; running 3 separate terminals loses the "one app" feel |
| **HuggingFace Router API** | Calls the LLM without needing a GPU | Free tier available, OpenAI-compatible endpoint, no credit card needed for class use | OpenAI API costs money and needs a card; Ollama runs locally but needs a capable GPU students may not have |
| **google/gemma-4-31b-it** | The LLM doing the actual generation | Strong instruction-following, good at structured output (food card format), HuggingFace-hosted | GPT-4 is proprietary and costs money; smaller models (Gemma 2B) produce weaker structured output; Qwen is also good but Gemma is a familiar Google name for students |
| **openai Python library** | HTTP client that calls HuggingFace router | Same library students will use if they switch to OpenAI later — one API pattern, multiple backends | `requests` library is more verbose and has no built-in streaming helpers; HuggingFace's own client uses a different interface pattern |
| **StreamingResponse + `yield`** | Sends tokens to the browser as they're generated | Makes the AI nature visually obvious — students see it "thinking" like ChatGPT | Returning the full response at once hides the LLM behaviour; WebSockets work but are overkill for one-directional streaming |
| **httpx** | Frontend proxies streaming requests to backends | Async-native, supports streaming reads from one service and writes to another cleanly | `requests` is synchronous — it would block the frontend while waiting for the LLM; `aiohttp` works but is more complex to configure |
| **Vanilla HTML + JS** | Landing page, forms, architecture diagram, health polling | No build step, no dependencies, works in any browser, easy to inspect in DevTools live | React/Vue adds a build pipeline that breaks the simplicity of the demo; Gradio would merge UI and logic into one service — exactly the monolith pattern we're arguing against |
| **`.env` file** | Stores `HF_TOKEN` outside the code | Separates config from code — 12-Factor principle 3; Docker Compose reads it automatically | Hardcoding the token in source is a security risk and bad practice; passing it manually every `docker run` is error-prone across 3 services |
| **`/health` endpoint** | Frontend polls each backend every 3 seconds | Makes service status visible in real time — the architecture diagram dots turn red live when you stop a service | No health check = silent failure, students wouldn't see the fault isolation moment clearly in the diagram |

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

> Read the full script once before the session to internalise the flow. Then use the step-by-step below during delivery — relevant lines are pulled in at each step.

---

### Full Script (read-through)

**A — File walkthrough**
- Open VS Code with the `poly-companion` folder visible in the sidebar
- "Before we run anything — let's read what we're about to run."
- Point at the three folders: "Three folders. Three services. One app."
- Open `docker-compose.yml`: "This is the only file that knows all three services exist. Each service block is self-contained — its own folder, its own port, its own container."
- Point at no `ports:` on backends: "The backends have no ports exposed. Students can't reach them directly. Everything goes through the frontend — like a real API gateway."
- Open `study-buddy/app.py`, scroll to `/health` and `/ask`: "Two endpoints. That's the entire surface area of this service. Health check so the system knows it's alive. Ask so the frontend can request an explanation."
- Point at `stream=True` and `yield token`: "These two lines are what make the response stream. Token by token, as fast as the model generates them."
- Open `makan-advisor/app.py`: "Same structure. Same pattern. Completely different job — food recommendations instead of explanations."
- ❓ Ask: "Do these two services need to talk to each other to do their jobs?"
- 💬 Expected: "No." → "Correct. They don't. They're completely independent. That's the point."

**B — Start and open**
- Switch to terminal: `docker-compose up --build`
- Point at interleaved output: "See the prefixes? `study-buddy` and `makan-advisor` building at the same time. Neither waits for the other."
- Wait for all three ready lines, then open browser: `http://localhost:7862`
- Point at two feature cards: "One URL. Two features. Students have no idea three containers are running underneath."
- Scroll to architecture diagram: "But we can see it. Three boxes, two arrows, live status dots. The green dots confirm all three services are up and talking."
- ❓ Ask: "Why do we only expose one port to the browser, not three?"
- 💬 Expected: anything around "security" or "one entry point" → "Exactly. One door in. The frontend controls what gets through. That's the API gateway pattern."

**C — Study Buddy**
- Click the Study Buddy card
- Type: "What is a microservice?" → level: Normal → submit
- Point at streaming output: "Watch it type itself out. Same experience as ChatGPT — because it's the same streaming pattern. Token by token, live."
- Submit again with level Simple: "Same service. Same container. Different system prompt — completely different output. The service adapts to the input, not to who calls it."
- ❓ Ask: "If I want to change the explanation style — do I redeploy the whole app?"
- 💬 Expected: "No, just the Study Buddy service." → "Right. Only the service that changed needs to be redeployed."

**D — Makan Advisor**
- Click the Makan Advisor card
- Point at the different UI: "Look at the inputs — dropdowns instead of a text box. Different job, different interface."
- Select Stressed / $4–$6 / No preference → submit
- Point at structured output: "Dish, location, price, pro tip — all streamed live. Same underlying pattern — one LLM call, one streaming response — scoped to one job."
- ❓ Ask: "Has Study Buddy been affected by anything we just did in Makan Advisor?"
- 💬 Expected: "No." → "No. They've never spoken to each other. No shared state, no shared code."

**E — The key moment**
- Open a new terminal: `docker-compose stop makan-advisor`
- Switch to browser, point at diagram: "Makan Advisor dot just turned red. The frontend's health check detected it within 3 seconds — without us doing anything."
- Click Makan Advisor card: "Red error card. Service is down. The frontend caught it and surfaced it clearly."
- Click Study Buddy, submit a question: "Still streaming. Still working. Didn't notice."
- ❓ Ask: "If this were a monolith — what would have happened when Makan Advisor broke?"
- 💬 Expected: "Everything goes down." → "Login, payment, cart — everything. One bug, total outage. This is fault isolation — the failure stayed in one box."

**F — Restart and close**
- `docker-compose start makan-advisor`
- Point at diagram: "Dot turns green. Study Buddy was never touched."
- "One command. Zero coordination. No other team needed to know."
- "In Kubernetes, this restart would happen automatically — before you even noticed it went down."
- Closing: "This is what a microservices architecture looks like running. Not a diagram — actual separate containers, separate code, independent lifecycles. What you just saw is how Grab, Shopee, Netflix run their features."

---

### Step 0 — Before touching the terminal

**What to show:** VS Code with `poly-companion` folder open in sidebar.

🎤 **Say:** "Before we run anything — let's read what we're about to run."

**Walk through each file:**

| File | Point at | Say |
|---|---|---|
| Folder structure | Three subfolders | "Three folders. Three services. One app." |
| `docker-compose.yml` | Service blocks, no `ports:` on backends | "Only one port exposed — everything goes through the frontend, like an API gateway." |
| `study-buddy/app.py` | `/health`, `/ask`, `stream=True`, `yield token` | "Two endpoints. Two lines make it stream." |
| `makan-advisor/app.py` | Same structure | "Same pattern, different job — food instead of explanations." |
| `.env.example` | `HF_TOKEN` line | "Token lives here, not in any code file. 12-Factor rule 3." |

❓ **Ask the class:** "Do these two services need to talk to each other?"  
💬 **Expected:** "No" → "Correct. Completely independent. That's the whole point."

📌 **S26 — What are Microservices?** One job, one codebase, one team per service.  
📌 **S29–32 — Why Microservices?** Flexibility, Reliability, Scalability, Agility — each one is visible in this file structure.

---

### Step 1 — Start everything

```bash
cd path\to\poly-companion
docker-compose up --build
```

👀 **Students notice:** Terminal shows interleaved lines prefixed `study-buddy |` and `makan-advisor |`

🎤 **Say:** "Both building at the same time. Neither waits for the other."

**Wait for all three ready lines:**
```
study-buddy   | Uvicorn running on http://0.0.0.0:7860
makan-advisor | Uvicorn running on http://0.0.0.0:7861
frontend      | Uvicorn running on http://0.0.0.0:7862
```

📌 **S33–36 — Containers** Each service packaged identically — runs the same everywhere Docker runs.

---

### Step 2 — Open the app

```
http://localhost:7862
```

👀 **Students notice:** Single landing page with two feature cards.

🎤 **Say:** "One URL. Two features. Three containers underneath — students using this app would never know."

**Scroll to the architecture diagram at the bottom.**

👀 **Students notice:** Three boxes, arrows, green status dots.

🎤 **Say:** "The diagram shows us what's actually running. Green dots — all three services up. The backends are sealed off — no direct browser access."

❓ **Ask:** "Why do we only expose one port — not three?"  
💬 **Expected:** "Security / one entry point" → "One door in. The frontend controls access. That's the API gateway pattern."

📌 **S39–40 — Kubernetes** docker-compose does this locally; K8s does it at scale across hundreds of containers.

---

### Step 3 — Demo Study Buddy

**Click Study Buddy card.** Enter: `What is a microservice?` → level: Normal → submit.

👀 **Students notice:** Text appears word by word.

🎤 **Say:** "Watch it type itself out. Same as ChatGPT — because it's the same streaming pattern. Token by token, as the model generates them."

**Submit again, same topic → level: Simple.**

👀 **Students notice:** Much shorter, simpler explanation from the same service.

🎤 **Say:** "Same service. Same container. Different system prompt — different output. The service adapts to the input."

❓ **Ask:** "If I want to change the explanation style — do I redeploy the whole app?"  
💬 **Expected:** "No, just Study Buddy." → "Exactly. Only the service that changed. Zero impact on Makan Advisor."

📌 **S14–15 — Cloud Native AI** The LLM is just another service called over an API. Streaming = real production AI pattern.  
📌 **AI hook payoff** This is the pattern behind every AI product they use daily.

---

### Step 4 — Demo Makan Advisor

**Click Makan Advisor card.** Select: Stressed / $4–$6 / No preference → submit.

👀 **Students notice:** Different UI (dropdowns, not a text box), structured output with emoji.

🎤 **Say:** "Different inputs, different output, different job. But underneath — same pattern. One LLM call, one streaming response, one responsibility."

🎤 **Say:** "Study Buddy and Makan Advisor have never spoken to each other. No shared state, no shared code."

❓ **Ask:** "Has anything we just did in Makan Advisor affected Study Buddy?"  
💬 **Expected:** "No." → "No. Loose coupling. Each service only knows about its own job."

📌 **S29 — Flexibility** Different teams could own each card — shipping independently, never stepping on each other.

---

### Step 5 — THE KEY MOMENT — Stop Makan Advisor

> Do this slowly. Pause before each narration line.

**Open a NEW terminal in the same folder:**

```bash
docker-compose stop makan-advisor
```

**Switch back to browser. Point at the architecture diagram.**

👀 **Students notice:** Makan Advisor dot turns red within 3 seconds.

🎤 **Say:** "The frontend's health check picked that up automatically. No one told it — it detected it."

**Click the Makan Advisor card.**

👀 **Students notice:** Red error card — "This service is currently down."

🎤 **Say:** "The frontend caught the failure and surfaced it clearly. Makan is down."

**Click Study Buddy. Submit a question.**

👀 **Students notice:** Still works. Still streaming.

🎤 **Say:** "Still working. Didn't notice. One service is down — the other is completely unaffected."

❓ **Ask:** "If this were a monolith — what would have happened?"  
💬 **Expected:** "Everything goes down." → "Login, cart, payment — everything. One bug, total outage. This is fault isolation — the failure stayed in one box."

📌 **S30 — Reliability / Fault Isolation** One service failing never cascades. This is why Netflix can run 1,000+ services without one bug taking down your queue.

---

### Step 6 — Restart and close

```bash
docker-compose start makan-advisor
```

👀 **Students notice:** Dot turns green. Makan Advisor card works again.

🎤 **Say:** "One command. Zero coordination with Study Buddy. No other team needed to know."

🎤 **Say:** "In Kubernetes, this restart would happen automatically — before you even noticed it went down."

**Closing line:**  
🎤 **Say:** "This is what a microservices architecture looks like running. Not a diagram — actual separate containers, separate code, independent lifecycles. What you just saw is how Grab, Shopee, and Netflix run their features."

❓ **Final open question:** "What's one thing you'd build as a microservice in your next project?"  
💬 **Let 2–3 students answer. No wrong answers. Close on their responses.**

📌 **K8s self-healing (new slides)** Desired state vs actual state — K8s reconciles automatically.  
📌 **S31–32 — Agility** Independent deployment: the Makan team shipped without a meeting, a sign-off, or touching Study Buddy.

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
