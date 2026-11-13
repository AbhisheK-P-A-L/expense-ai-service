# Expense AI Service ⚡

High-performance, tenant-isolated AI microservice for natural language expense extraction, AST-safe NL-to-SQL query compilation, and personalized spending insights. Built with **FastAPI**, **Groq LLM (Qwen/Llama)**, and **PostgreSQL**.

Part of the **AI-Powered Natural Language Expense Tracker** distributed architecture.

---

## 🌟 Key Features

1. **Zero-Click Natural Language Expense Parsing (`POST /parse-expense`)**:
   - Converts conversational inputs like *"Spent 450 rupees on lunch at Subway yesterday"* into structured expense entries (`amount`, `category`, `vendor`, `date`, `description`).
   - Uses temporal anchoring against today's date and strict JSON-schema enforcement (`temperature: 0.0`).

2. **Validator-Planner-Executor NL-to-SQL Pipeline (`POST /nl-query`)**:
   - **Stage 1 (Validator)**: AST token inspection blocking SQL injection, comment delimiters (`;`, `--`, `/*`, `#`), and destructive DDL/DML mutation keywords (`DROP`, `DELETE`, `UPDATE`, `ALTER`, etc.).
   - **Stage 2 (Planner)**: Translates user intent into a deterministic `QueryPlan` with relative date boundaries and aggregation types (`SUM`, `AVG`, `COUNT`, `MAX`, `MIN`, `LIST`).
   - **Stage 3 (Executor)**: Compiles and executes parameterized SQL with non-bypassable tenant isolation (`WHERE e.user_id = %s`), completely eliminating cross-tenant query exposure.

3. **Contextual AI Spending Insights (`POST /generate-insights` & `POST /user-insights`)**:
   - Analyzes spending patterns across categories and top vendors to generate actionable financial advice.
   - Direct PostgreSQL integration for instant summary aggregation.

---

## 🏗️ Architecture Overview

```
┌──────────────────────────────────────────────┐
│           Spring Boot Backend API            │
│  - JWT Authentication & RBAC                 │
│  - Trie Autocomplete (O(L))                  │
│  - LRU In-Memory Cache (O(1))                │
│  - Analytics DAG Planner (CompletableFuture) │
│  - Scheduled Bounded Batch Insights          │
└──────────────────────┬───────────────────────┘
                       │ HTTP REST
                       ▼
┌──────────────────────────────────────────────┐
│          Expense AI Microservice (FastAPI)   │
│  - Groq LLM Inference (Deterministic JSON)   │
│  - AST Security Validator                    │
│  - Safe SQL Query Planner & Compiler         │
│  - Multi-Tenant SQL Isolation Engine         │
└──────────────────────┬───────────────────────┘
                       │ Parameterized SQL
                       ▼
┌──────────────────────────────────────────────┐
│          PostgreSQL Database (Supabase)      │
│  - expenses, categories, users               │
└──────────────────────────────────────────────┘
```

---

## 🚀 API Endpoints

### 1. Health Check
`GET /health`
```json
{
  "status": "ok"
}
```

### 2. Parse Natural Language Expense
`POST /parse-expense`
```json
// Request
{
  "text": "Bought shoes from Myntra for 2800 yesterday"
}

// Response
{
  "amount": 2800.0,
  "currency": "INR",
  "category": "SHOPPING",
  "vendor": "Myntra",
  "description": "Shoes purchase",
  "expenseDate": "2026-11-12"
}
```

### 3. Safe Natural Language Query (NL-to-SQL)
`POST /nl-query`
```json
// Request
{
  "userId": "11111111-1111-1111-1111-111111111111",
  "query": "How much did I spend on food this month?"
}

// Response
{
  "originalQuery": "How much did I spend on food this month?",
  "intentDescription": "Total spending on FOOD category for the current month",
  "aggregationType": "SUM",
  "aggregatedValue": 4600.0,
  "countValue": null,
  "records": [],
  "summary": "Calculated SUM is ₹4,600.00."
}
```

### 4. Fetch Insights by User ID
`POST /user-insights`
```json
// Request
{
  "userId": "11111111-1111-1111-1111-111111111111",
  "days": 30
}

// Response
{
  "insights": [
    "Travel expenses (₹4,500) account for 37.8% of total spending; booking in advance could save up to 20%.",
    "Food is your highest category at ₹4,600 with Blinkit as a primary vendor; consider a weekly grocery plan."
  ]
}
```

---

## 🛠️ Local Development & Setup

1. **Clone and setup virtual environment**:
```bash
git clone https://github.com/AbhisheK-P-A-L/expense-ai-service.git
cd expense-ai-service

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

2. **Configure Environment Variables (`.env`)**:
```env
GROQ_API_KEY=your_groq_api_key
GROQ_MODEL=qwen/qwen3.8-27b
PORT=8000

DB_HOST=aws-1-ap-southeast-2.pooler.supabase.com
DB_PORT=5432
DB_NAME=postgres
DB_USER=postgres.your_project
DB_PASSWORD=your_password
```

3. **Run the server**:
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## 🐳 Docker & AWS Deployment

```bash
# Build Docker image
docker build -t expense-ai-service .

# Run container with environment file
docker run -d \
  --name expense-ai-service \
  --restart unless-stopped \
  --env-file .env \
  -p 8000:8000 \
  expense-ai-service
```
