import os
import json
from datetime import date
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from groq import Groq
from dotenv import load_dotenv
from app.database import fetch_user_expense_summary
from app.validator import validate_nl_query
from app.planner import generate_query_plan
from app.executor import execute_query_plan

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


class ExpenseSummary(BaseModel):
    """Summary data sent by Spring Boot for insight generation."""
    totalSpent: float
    categoryBreakdown: dict[str, float]   # e.g. {"FOOD": 3200, "TRAVEL": 1500}
    topVendors: list[str] = []            # e.g. ["Swiggy", "Amazon"]
    expenseCount: int
    periodDays: int = 30                  # how many days this summary covers


class UserInsightRequest(BaseModel):
    userId: str
    days: int = 30


class NLQueryRequest(BaseModel):
    userId: str
    query: str


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

GENERATE_INSIGHTS_PROMPT = """You are a personal finance advisor. Given the user's expense summary, generate 3-5 short, actionable spending insights.
Return ONLY valid JSON, no explanation, no markdown backticks.

Schema:
{
  "insights": [
    "<insight string>",
    ...
  ]
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


@app.post("/generate-insights")
def generate_insights(req: ExpenseSummary):
    """Takes expense summary data and returns AI-generated spending insights."""

    # Build a readable summary string for the LLM
    summary_text = (
        f"Total spent: ₹{req.totalSpent} over {req.periodDays} days across {req.expenseCount} expenses.\n"
        f"Category breakdown: {json.dumps(req.categoryBreakdown)}\n"
        f"Top vendors: {', '.join(req.topVendors) if req.topVendors else 'N/A'}"
    )

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": GENERATE_INSIGHTS_PROMPT},
            {"role": "user", "content": summary_text}
        ],
        temperature=0.3,  # Slightly creative for useful advice
        response_format={"type": "json_object"}
    )

    raw = response.choices[0].message.content.strip()

    try:
        parsed = json.loads(raw)
        insights = parsed.get("insights", [])
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="LLM returned invalid JSON")

    return {"insights": insights}


@app.post("/user-insights")
def get_user_insights_from_db(req: UserInsightRequest):
    """Fetches user expenses directly from PostgreSQL and generates AI spending insights."""
    try:
        summary_data = fetch_user_expense_summary(user_id=req.userId, days=req.days)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database query failed: {e}")

    summary = ExpenseSummary(**summary_data)
    return generate_insights(summary)


@app.post("/nl-query")
def process_natural_language_query(req: NLQueryRequest):
    """
    3-Stage Natural Language to SQL Pipeline:
    1. Validator: AST security & injection prevention
    2. Planner: Deterministic LLM query planning with temporal anchoring
    3. Executor: Parameterized tenant-isolated SQL query execution
    """
    # Stage 1: Validation
    validate_nl_query(req.query)

    # Stage 2: Planning
    try:
        plan = generate_query_plan(req.query)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query planning failed: {e}")

    # Stage 3: Execution
    try:
        result = execute_query_plan(user_id=req.userId, original_query=req.query, plan=plan)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query execution failed: {e}")

    return result
