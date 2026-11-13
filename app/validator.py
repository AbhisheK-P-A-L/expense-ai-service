import re
from fastapi import HTTPException

# Dangerous SQL / DDL / DML mutation keywords and privilege escalation tokens
FORBIDDEN_KEYWORDS = {
    "DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "TRUNCATE", "CREATE",
    "REPLACE", "MERGE", "GRANT", "REVOKE", "EXEC", "EXECUTE", "SHUTDOWN",
    "XP_CMDSHELL", "INFORMATION_SCHEMA", "PG_CATALOG", "PG_USER", "PG_SHADOW",
    "INTO OUTFILE", "INTO DUMPFILE", "LOAD DATA", "SLEEP", "BENCHMARK",
    "UNION SELECT", "UNION ALL SELECT"
}

# SQL comment tokens and statement delimiters
COMMENT_PATTERN = re.compile(r"(--|/\*|\*/|#|;)")


def validate_nl_query(raw_query: str) -> None:
    """
    Validates natural language input against SQL injection, DDL/DML mutation keywords,
    comment tokens, and character length limits.
    """
    if not raw_query or not raw_query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    if len(raw_query) > 500:
        raise HTTPException(status_code=400, detail="Query exceeds maximum length of 500 characters.")

    # 1. Reject comment characters and statement terminations
    if COMMENT_PATTERN.search(raw_query):
        raise HTTPException(
            status_code=400,
            detail="Query contains prohibited SQL meta-characters or comment tokens."
        )

    # 2. Reject forbidden SQL keywords
    for keyword in FORBIDDEN_KEYWORDS:
        pattern = r"\b" + re.escape(keyword) + r"\b"
        if re.search(pattern, raw_query, re.IGNORECASE):
            raise HTTPException(
                status_code=400,
                detail=f"Query rejected: Prohibited SQL keyword detected."
            )
