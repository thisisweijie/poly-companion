import os
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from openai import OpenAI

# ─────────────────────────────────────────────────────────
# Poly Student Companion — Makan Advisor backend
#
# Pure REST API. No UI. One job: take mood, budget and diet,
# stream back a hawker food recommendation.
#
# Completely independent of Study Buddy.
# Different responsibility, different container, different port.
# ─────────────────────────────────────────────────────────

app = FastAPI()

client = OpenAI(
    base_url="https://router.huggingface.co/v1",
    api_key=os.environ.get("HF_TOKEN"),
)

MODEL = "google/gemma-4-31B-it"

SYSTEM_PROMPT = """
You are a friendly Singapore hawker food advisor for polytechnic students.
Given a student's mood, budget and dietary preference, recommend ONE specific hawker dish.

Format your response exactly like this:
🍽️  Dish: [dish name]
📍  Where to get it: [type of hawker stall]
💰  Estimated price: [price range in SGD]
💬  Why this fits your mood: [1-2 sentence reason, warm and friendly tone]
🔥  Pro tip: [one practical tip]

Only recommend real Singapore hawker food. Keep it short and fun.
"""


class RecommendRequest(BaseModel):
    mood: str
    budget: str
    diet: str


@app.get("/health")
def health():
    return {"status": "up", "service": "makan-advisor"}


@app.post("/recommend")
def recommend(req: RecommendRequest):
    user_message = (
        f"My mood: {req.mood}\n"
        f"My budget: {req.budget}\n"
        f"Dietary preference: {req.diet}\n"
        f"What should I eat?"
    )

    def generate():
        stream = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            max_tokens=300,
            stream=True,
        )
        for chunk in stream:
            token = chunk.choices[0].delta.content or ""
            if token:
                yield token

    return StreamingResponse(generate(), media_type="text/plain")
