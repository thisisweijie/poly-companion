import os
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from openai import OpenAI

app = FastAPI()

# Same client setup as study-buddy — HF router is OpenAI-compatible,
# so we reuse the same library. Both services are independent but happen
# to use the same model. That's fine — they don't share any state.
client = OpenAI(
    base_url="https://router.huggingface.co/v1",
    api_key=os.environ.get("HF_TOKEN"),
)

MODEL = "google/gemma-4-31b-it"

# The format in this prompt matters a lot — if you change the emoji or field names,
# update the frontend CSS too since the output renders as preformatted text.
# Gemma follows formatting instructions pretty well but test if you swap models.
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
    # Structured as separate lines so the model treats each field distinctly.
    # Lumping it into one sentence tends to produce weaker recommendations.
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
            max_tokens=300,  # food rec doesn't need much — 300 is plenty, keeps latency low
            stream=True,
        )
        for chunk in stream:
            token = chunk.choices[0].delta.content or ""
            if token:
                yield token

    return StreamingResponse(generate(), media_type="text/plain")
