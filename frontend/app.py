import os
import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

# ─────────────────────────────────────────────────────────
# Poly Student Companion — Frontend
#
# Serves the landing page and proxies requests to the two
# backend microservices. Students only ever see this port.
#
# Study Buddy  → http://study-buddy:7860
# Makan Advisor → http://makan-advisor:7861
# ─────────────────────────────────────────────────────────

app = FastAPI()

# Read backend URLs from env — docker-compose injects these at runtime.
# Defaults point to Docker's internal hostnames, so this just works locally.
# If you ever run these services elsewhere, update the env vars, not this file.
STUDY_BUDDY_URL   = os.environ.get("STUDY_BUDDY_URL",   "http://study-buddy:7860")
MAKAN_ADVISOR_URL = os.environ.get("MAKAN_ADVISOR_URL", "http://makan-advisor:7861")


# ── Health check proxy ────────────────────────────────────

@app.get("/health")
async def health():
    statuses = {}
    # Short timeout on purpose — if a backend doesn't respond in 2s it's effectively down.
    # Don't raise this; a slow response is as bad as no response for the demo's status dots.
    async with httpx.AsyncClient(timeout=2.0) as client:
        for name, url in [("study-buddy", STUDY_BUDDY_URL), ("makan-advisor", MAKAN_ADVISOR_URL)]:
            try:
                r = await client.get(f"{url}/health")
                statuses[name] = "up" if r.status_code == 200 else "down"
            except Exception:
                # Connection refused, timeout, DNS failure — all mean the same thing: down.
                statuses[name] = "down"
    return statuses


# ── Streaming proxies ─────────────────────────────────────

class AskRequest(BaseModel):
    topic: str
    level: str


class RecommendRequest(BaseModel):
    mood: str
    budget: str
    diet: str


@app.post("/ask")
async def ask(req: AskRequest):
    async def stream():
        try:
            # 60s timeout — LLM calls can be slow, especially on first token.
            # Don't lower this or you'll get timeouts mid-stream on longer explanations.
            async with httpx.AsyncClient(timeout=60.0) as client:
                async with client.stream(
                    "POST", f"{STUDY_BUDDY_URL}/ask", json=req.model_dump()
                ) as r:
                    if r.status_code != 200:
                        yield "SERVICE_ERROR"
                        return
                    # Forward each chunk as it arrives — we're a pass-through, not a buffer.
                    # Buffering would defeat the whole point of streaming.
                    async for chunk in r.aiter_text():
                        yield chunk
        except Exception:
            # Sentinel value the JS checks for — cleaner than trying to set HTTP status
            # codes mid-stream once streaming has already started.
            yield "SERVICE_DOWN"
    return StreamingResponse(stream(), media_type="text/plain")


@app.post("/recommend")
async def recommend(req: RecommendRequest):
    async def stream():
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                async with client.stream(
                    "POST", f"{MAKAN_ADVISOR_URL}/recommend", json=req.model_dump()
                ) as r:
                    if r.status_code != 200:
                        yield "SERVICE_ERROR"
                        return
                    async for chunk in r.aiter_text():
                        yield chunk
        except Exception:
            yield "SERVICE_DOWN"
    return StreamingResponse(stream(), media_type="text/plain")



# ── Landing page ──────────────────────────────────────────
# HTML lives in templates/index.html — keeps this file readable
# and means designers can touch the UI without opening app.py.
# Jinja2 is FastAPI's standard templating engine; Request is required
# by Jinja2Templates even if we're not passing template variables.

templates = Jinja2Templates(directory="templates")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request, "index.html")
