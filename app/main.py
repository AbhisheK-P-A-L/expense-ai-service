import os
import json
from datetime import date
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from groq import Groq
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Create the FastAPI app
app = FastAPI()

# Initialize Groq client (reads GROQ_API_KEY from environment)
client = Groq(api_key=os.getenv("GROQ_API_KEY"))
MODEL = os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b")


# ---------- Request / Response models ----------
# These are like your Java DTOs, but Pydantic auto-validates them

class ParseExpenseRequest(BaseModel):
    text: str  # e.g. "spent 500 on dinner yesterday"


class ParsedExpense(BaseModel):
    amount: float
    currency: str = "INR"
    category: str
    vendor: str | None = None       # can be null
    description: str
    expenseDate: str                 # "YYYY-MM-DD"


# ---------- Prompts ----------

PARSE_EXPENSE_PROMPT = """You are an expense parser. Extract structured data from the user's text.
Return ONLY valid JSON, no explanation, no markdown backticks.

Schema:
{
  "amount": <number>,
  "currency": "<3-letter ISO code, default INR>",
  "category": "<one of: FOOD, SHOPPING, TRAVEL, HEALTH, ENTERTAINMENT, UTILITIES, OTHER>",
  "vendor": "<merchant name or null>",
  "description": "<short description, max 10 words>",
  "expenseDate": "<YYYY-MM-DD, use today's date if not mentioned>"
}"""


# ---------- Endpoints ----------

@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post("/parse-expense")
def parse_expense(req: ParseExpenseRequest):
    """Takes natural language like 'spent 500 on dinner yesterday'
    and returns structured expense data."""

    if not req.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    # Inject today's date into the prompt so the LLM knows what "yesterday" means
    prompt = PARSE_EXPENSE_PROMPT + f"\n\nToday's date is {date.today()}"

    # Call Groq LLM — this single call does parsing + validation in one shot
    # response_format={"type": "json_object"} forces the LLM to return ONLY valid JSON
    # (no extra text, no markdown backticks — guaranteed by Groq's API)
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": req.text}
        ],
        temperature=0.0,  # Deterministic output for consistent parsing
        response_format={"type": "json_object"}
    )

    # Extract the LLM's response text
    raw = response.choices[0].message.content.strip()

    # Parse the JSON string and validate it has the exact fields we expect
    try:
        parsed = json.loads(raw)
        result = ParsedExpense(**parsed)  # This throws if any required field is missing/wrong
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="LLM returned invalid JSON")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM response missing required fields: {e}")

    return result
