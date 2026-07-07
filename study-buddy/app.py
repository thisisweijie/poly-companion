import os
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from openai import OpenAI

app = FastAPI()

# Using the openai client here even though we're hitting HuggingFace —
# HF router exposes an OpenAI-compatible endpoint, so we get streaming
# and all the nice helpers for free without writing raw HTTP calls.
client = OpenAI(
    base_url="https://router.huggingface.co/v1",
    api_key=os.environ.get("HF_TOKEN"),  # never hardcode this, comes from .env via docker-compose
)

MODEL = "google/gemma-4-31b-it"

# Each level maps to a different system prompt — same service, same endpoint,
# completely different output depending on what the frontend sends.
# If you want to add a new level later, just add a key here. No other changes needed.
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
    level: str  # expected: "simple" | "normal" | "technical"


# The frontend polls this every 3 seconds to check if this service is alive.
# Keep it cheap — just return 200. No DB calls, no LLM calls.
@app.get("/health")
def health():
    return {"status": "up", "service": "study-buddy"}


@app.post("/ask")
def ask(req: AskRequest):
    # Fall back to "normal" if the frontend sends something unexpected
    prompt = LEVEL_PROMPTS.get(req.level, LEVEL_PROMPTS["normal"])

    def generate():
        stream = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": f"Explain this: {req.topic}"},
            ],
            max_tokens=400,
            stream=True,  # ask the model to send tokens as they're generated, not all at once
        )
        for chunk in stream:
            token = chunk.choices[0].delta.content or ""
            if token:
                yield token  # push each token straight to the response — this is what makes it feel like ChatGPT

    # StreamingResponse wraps the generator — FastAPI handles the chunked HTTP transfer
    return StreamingResponse(generate(), media_type="text/plain")
