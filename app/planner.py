import os
import json
from datetime import date
from typing import Literal
from pydantic import BaseModel, Field
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))
MODEL = os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b")

AggregationType = Literal["SUM", "AVG", "COUNT", "MAX", "MIN", "LIST"]


class QueryPlan(BaseModel):
    aggregationType: AggregationType = "SUM"
    categoryName: str | None = None
    vendor: str | None = None
    descriptionKeyword: str | None = None
    startDate: str | None = None          # YYYY-MM-DD
    endDate: str | None = None            # YYYY-MM-DD
    minAmount: float | None = None
    maxAmount: float | None = None
    limit: int = Field(default=50, ge=1, le=200)
    intentDescription: str = "Spending analysis"


PLANNER_SYSTEM_PROMPT = """You are a deterministic SQL query planner for an expense tracking database.
Analyze the user's spending question and convert it into a structured JSON query plan.

Available categories in system: FOOD, TRAVEL, SHOPPING, HEALTH, ENTERTAINMENT, UTILITIES, OTHER.
Allowed Aggregation Types: "SUM", "AVG", "COUNT", "MAX", "MIN", "LIST".

Schema:
{
  "aggregationType": "<SUM | AVG | COUNT | MAX | MIN | LIST>",
  "categoryName": "<category name or null>",
  "vendor": "<merchant/vendor name or null>",
  "descriptionKeyword": "<keyword or null>",
  "startDate": "<YYYY-MM-DD or null>",
  "endDate": "<YYYY-MM-DD or null>",
  "minAmount": <number or null>,
  "maxAmount": <number or null>,
  "limit": <number, default 50>,
  "intentDescription": "<brief explanation of what is being queried>"
}

Return ONLY valid JSON matching this schema, without explanations or markdown backticks."""


def generate_query_plan(user_query: str) -> QueryPlan:
    """
    Translates natural language questions into an intermediate structured QueryPlan
    with temporal anchoring against today's date.
    """
    today = date.today()
    system_prompt = (
        PLANNER_SYSTEM_PROMPT + 
        f"\n\nToday's date is {today.isoformat()} ({today.strftime('%A')})."
    )

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_query}
        ],
        temperature=0.0,  # Deterministic planning
        response_format={"type": "json_object"}
    )

    raw_json = response.choices[0].message.content.strip()
    parsed = json.loads(raw_json)
    return QueryPlan(**parsed)
