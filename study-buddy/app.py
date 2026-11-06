import os
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from openai import OpenAI, RateLimitError

app = FastAPI()

# Using the openai client here even though we're hitting Groq —
# Groq exposes an OpenAI-compatible endpoint, so we get streaming
# and all the nice helpers for free without writing raw HTTP calls.
# Provider, key and model all come from env vars (see .env.example) —
# same OpenAI-compatible interface, no rewrite needed.
client = OpenAI(
    base_url=os.environ.get("LLM_BASE_URL", "https://api.groq.com/openai/v1"),
    api_key=os.environ.get("LLM_API_KEY"),  # from .env via docker-compose
)

MODEL = os.environ.get("LLM_MODEL", "openai/gpt-oss-20b")

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
        "Explain this topic in technical depth for someone with programming experience. "
        "Use exactly three short sections with bold headings: "
        "What it is, How it works under the hood, Practical use case. "
        "Use the correct technical terms, and include one concrete detail per section "
        "(a protocol, command, data structure or component name). "
        "Keep it under 300 words. No diagrams, tables or ASCII art."
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
        # The HTTP response has already started by the time the LLM call runs, so an error
        # can't become a status code. Send a short marker word instead; the page shows a
        # friendly message for it. Without this, a rate limit looked like "service down".
        try:
            stream = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": f"Explain this: {req.topic}"},
                ],
                extra_body={"reasoning_effort": "low"},  # less hidden thinking: faster, and uses fewer free-tier tokens
                max_tokens=1500,  # reasoning model: hidden thinking counts against this limit, 400 cut answers off
                stream=True,  # ask the model to send tokens as they're generated, not all at once
            )
            for chunk in stream:
                token = chunk.choices[0].delta.content or ""
                if token:
                    yield token  # push each token straight to the response
        except RateLimitError:
            yield "RATE_LIMITED"
        except Exception:
            yield "LLM_ERROR"

    # StreamingResponse wraps the generator — FastAPI handles the chunked HTTP transfer
    return StreamingResponse(generate(), media_type="text/plain")
