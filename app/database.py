import os
from datetime import date, timedelta
import psycopg2
from psycopg2.extras import RealDictCursor

def get_db_connection():
    """Create and return a connection to the PostgreSQL database."""
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        database=os.getenv("DB_NAME", "expense_tracker"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", "postgres"),
    )
    return conn


def fetch_user_expense_summary(user_id: str, days: int = 30) -> dict:
    """
    Fetches aggregate expense data for a user over the last `days` days.
    Matches the schema and aggregations from the Spring Boot service:
    - Total spend & count
    - Breakdown by category
    - Top recent/highest vendors
    """
    start_date = date.today() - timedelta(days=days)

    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # 1. Category breakdown and totals
            cur.execute("""
                SELECT 
                    COALESCE(c.name, 'Uncategorized') AS category,
                    COALESCE(SUM(e.amount), 0) AS total_amount,
                    COUNT(e.id) AS count
                FROM expenses e
                LEFT JOIN categories c ON e.category_id = c.id
                WHERE e.user_id = %s AND e.date >= %s
                GROUP BY COALESCE(c.name, 'Uncategorized')
            """, (user_id, start_date))
            category_rows = cur.fetchall()

            # 2. Distinct top vendors
            cur.execute("""
                SELECT DISTINCT vendor
                FROM expenses
                WHERE user_id = %s AND e.date >= %s AND vendor IS NOT NULL AND vendor <> ''
                LIMIT 5
            """.replace("e.date", "date"), (user_id, start_date))
            vendor_rows = cur.fetchall()

    total_spent = sum(float(r["total_amount"]) for r in category_rows)
    expense_count = sum(int(r["count"]) for r in category_rows)
    category_breakdown = {r["category"]: float(r["total_amount"]) for r in category_rows}
    top_vendors = [r["vendor"] for r in vendor_rows]

    return {
        "totalSpent": total_spent,
        "expenseCount": expense_count,
        "categoryBreakdown": category_breakdown,
        "topVendors": top_vendors,
        "periodDays": days
    }
