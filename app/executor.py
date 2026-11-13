from typing import Any
from app.database import get_db_connection
from app.planner import QueryPlan
from psycopg2.extras import RealDictCursor


def execute_query_plan(user_id: str, original_query: str, plan: QueryPlan) -> dict[str, Any]:
    """
    Stage 3: Compiles safe, parameterized SQL with mandatory tenant isolation (e.user_id = %s).
    Executes against PostgreSQL without string interpolation vulnerabilities.
    """
    if not user_id:
        raise ValueError("user_id is required for tenant-scoped query execution.")

    where_clauses = ["e.user_id = %s"]
    params: list[Any] = [user_id]

    if plan.startDate:
        where_clauses.append("e.date >= %s")
        params.append(plan.startDate)

    if plan.endDate:
        where_clauses.append("e.date <= %s")
        params.append(plan.endDate)

    if plan.categoryName and plan.categoryName.strip():
        where_clauses.append("LOWER(c.name) LIKE LOWER(%s)")
        params.append(f"%{plan.categoryName.strip()}%")

    if plan.vendor and plan.vendor.strip():
        where_clauses.append("LOWER(e.vendor) LIKE LOWER(%s)")
        params.append(f"%{plan.vendor.strip()}%")

    if plan.descriptionKeyword and plan.descriptionKeyword.strip():
        where_clauses.append("LOWER(e.title) LIKE LOWER(%s) OR LOWER(e.description) LIKE LOWER(%s)")
        params.append(f"%{plan.descriptionKeyword.strip()}%")
        params.append(f"%{plan.descriptionKeyword.strip()}%")

    if plan.minAmount is not None:
        where_clauses.append("e.amount >= %s")
        params.append(plan.minAmount)

    if plan.maxAmount is not None:
        where_clauses.append("e.amount <= %s")
        params.append(plan.maxAmount)

    where_sql = " WHERE " + " AND ".join(where_clauses)
    is_list = (plan.aggregationType == "LIST")

    if plan.aggregationType == "COUNT":
        select_clause = "SELECT COUNT(e.id) AS count_val"
    elif plan.aggregationType == "AVG":
        select_clause = "SELECT COALESCE(AVG(e.amount), 0) AS agg_val"
    elif plan.aggregationType == "MAX":
        select_clause = "SELECT COALESCE(MAX(e.amount), 0) AS agg_val"
    elif plan.aggregationType == "MIN":
        select_clause = "SELECT COALESCE(MIN(e.amount), 0) AS agg_val"
    elif is_list:
        select_clause = """
            SELECT 
                e.id, 
                e.title, 
                e.amount, 
                e.currency, 
                e.date, 
                e.vendor, 
                e.description, 
                c.name AS category
        """
    else:  # default SUM
        select_clause = "SELECT COALESCE(SUM(e.amount), 0) AS agg_val"

    query_sql = f"""
        {select_clause}
        FROM expenses e
        LEFT JOIN categories c ON e.category_id = c.id
        {where_sql}
    """

    if is_list:
        query_sql += " ORDER BY e.date DESC, e.created_at DESC LIMIT %s"
        params.append(plan.limit)

    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query_sql, tuple(params))
            
            agg_value = None
            count_value = None
            records = []

            if is_list:
                records = cur.fetchall()
                count_value = len(records)
                # Convert date and numeric fields for JSON serialization
                for r in records:
                    r["amount"] = float(r["amount"])
                    r["date"] = r["date"].isoformat() if r["date"] else None
                summary = f"Found {count_value} matching expense record(s)."
            elif plan.aggregationType == "COUNT":
                row = cur.fetchone()
                count_value = int(row["count_val"]) if row else 0
                summary = f"Total count: {count_value} transaction(s) matching your criteria."
            else:
                row = cur.fetchone()
                agg_value = round(float(row["agg_val"]), 2) if row else 0.0
                summary = f"Calculated {plan.aggregationType} is ₹{agg_value:,.2f}."

    return {
        "originalQuery": original_query,
        "intentDescription": plan.intentDescription,
        "aggregationType": plan.aggregationType,
        "aggregatedValue": agg_value,
        "countValue": count_value,
        "records": records,
        "summary": summary
    }
