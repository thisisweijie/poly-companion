import os
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from openai import OpenAI

# ─────────────────────────────────────────────────────────
# Poly Student Companion — Study Buddy backend
#
# Pure REST API. No UI. One job: take a topic and level,
# stream back an explanation from the LLM.
#
# The frontend calls this service. It knows nothing about
# the Makan Advisor service — completely independent.
# ─────────────────────────────────────────────────────────

app = FastAPI()

client = OpenAI(
    base_url="https://router.huggingface.co/v1",
    api_key=os.environ.get("HF_TOKEN"),
)

MODEL = "google/gemma-4-31B-it"

LEVEL_PROMPTS = {
    "simple": (
        "Explain this topic as if talking to a 12-year-old. "
        "Use a short everyday analogy. Maximum 4 sentences."
    ),
    "normal": (
        "Explain this topic for a polytechnic student in Singapore. "
        "Use plain language and give one real-world example. Be concise."
    ),
    "technical": (
        "Explain this topic in technical depth. "
        "Cover: what it is, how it works under the hood, and one practical use case. "
        "Use clear sections."
    ),
}


class AskRequest(BaseModel):
    topic: str
    level: str  # "simple" | "normal" | "technical"


@app.get("/health")
def health():
    return {"status": "up", "service": "study-buddy"}


@app.post("/ask")
def ask(req: AskRequest):
    prompt = LEVEL_PROMPTS.get(req.level, LEVEL_PROMPTS["normal"])

    def generate():
        stream = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": f"Explain this: {req.topic}"},
            ],
            max_tokens=400,
            stream=True,
        )
        for chunk in stream:
            token = chunk.choices[0].delta.content or ""
            if token:
                yield token

    return StreamingResponse(generate(), media_type="text/plain")
