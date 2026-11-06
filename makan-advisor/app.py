import os
import random
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from openai import OpenAI, RateLimitError

app = FastAPI()

# Same client setup as study-buddy — OpenAI-compatible endpoint, configured via env vars.
# Both services are independent: each picks its own model, so one service using up its
# daily token allowance doesn't stop the other. They don't share any state.
client = OpenAI(
    base_url=os.environ.get("LLM_BASE_URL", "https://api.groq.com/openai/v1"),
    api_key=os.environ.get("LLM_API_KEY"),  # from .env via docker-compose
)

# A larger model than study-buddy uses: it knows Singapore food better, and Groq counts
# each model's free daily tokens separately.
MODEL = os.environ.get("LLM_MODEL", "openai/gpt-oss-120b")

# The format in this prompt matters a lot — if you change the emoji or field names,
# update the frontend CSS too since the output renders as preformatted text.
# Models vary in how well they follow this format, so re-test if you swap models.
SYSTEM_PROMPT = """
You are a friendly Singapore food advisor. People here eat at hawker centres, kopitiams
and food courts every day, and you know all of it.
Given someone's mood, budget and dietary preference, recommend ONE specific local dish.

Be adventurous and varied. Draw from everything Singapore eats: Chinese (Hokkien, Teochew,
Cantonese, Hainanese, Hakka and more), Malay, Indian, Peranakan, Eurasian, and local fusion,
including breakfast items, snacks, desserts and drinks. Do not default to the most famous
or touristy dish. Prefer the local favourites that Singaporeans actually queue for, and
surprise the person with a good pick that fits their mood.

Only recommend well-known dishes that most Singaporeans would recognise by name and that are
sold at ordinary hawker centres, kopitiams or food courts. If you are not certain a dish
really exists in Singapore, pick a different one. Describe the dish accurately: say what it
really is and how it is really served.

Respect the dietary preference strictly, including hidden ingredients:
- Halal: only dishes from Malay or Indian-Muslim stalls or halal-certified outlets, and tell
  them to look for the MUIS Halal certificate.
- Vegetarian: only dishes that really can be made fully vegetarian, and say to ask for the
  vegetarian version or go to a vegetarian stall.
- No pork: no pork, lard or pork-based broth.
- No seafood: no fish, prawn, cockles, fishcake, dried fish or shrimp paste.

The dish must fit the budget at real Singapore hawker and food-court prices in SGD. Give an
honest range, not an exact price. Even for the biggest budget, stay under about $12.

Format your response exactly like this:
🍽️  Dish: [dish name]
💰  Estimated price: [price range in SGD]
💬  Why this fits your mood: [1-2 sentence reason, warm and friendly tone, a light touch of Singlish is fine]
🔥  Pro tip: [one practical tip, like how to order it or what to add]

Only recommend real Singapore hawker food. Keep it short and fun.
"""


# A random food culture is suggested on every request. LLMs love picking the same famous dish
# every time, so this nudges each answer in a different direction without listing any dishes.
# It is only a nudge: the diet and mood still come first.
FOOD_CULTURES = [
    "Hokkien", "Teochew", "Cantonese", "Hainanese", "Hakka",
    "Malay", "Indian", "Indian-Muslim", "Peranakan", "Eurasian",
]

# Same idea for the kind of food, so answers aren't always a rice or noodle plate.
FOOD_TYPES = [
    "rice dish", "noodle dish", "soup", "snack or kueh", "dessert",
    "breakfast item", "dish with a gravy or curry", "grilled or fried item",
]


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
        f"For variety, lean towards {random.choice(FOOD_CULTURES)} food and a "
        f"{random.choice(FOOD_TYPES)} this time, "
        f"but ignore that if it doesn't suit my diet, budget or mood.\n"
        f"What should I eat?"
    )

    def generate():
        # The HTTP response has already started by the time the LLM call runs, so an error
        # can't become a status code. Send a short marker word instead; the page shows a
        # friendly message for it. Without this, a rate limit looked like "service down".
        try:
            stream = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.8,  # some randomness for variety, but 1.0 made it invent dishes and stalls
                extra_body={"reasoning_effort": "medium"},  # low effort guessed more; medium checks its facts better
                max_tokens=3000,  # gpt-oss spends tokens on hidden reasoning first; 300 and 1000 both returned empty replies
                stream=True,
            )
            for chunk in stream:
                token = chunk.choices[0].delta.content or ""
                if token:
                    yield token
        except RateLimitError:
            yield "RATE_LIMITED"
        except Exception:
            yield "LLM_ERROR"

    return StreamingResponse(generate(), media_type="text/plain")
