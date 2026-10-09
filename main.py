import logging
import os
import re
from datetime import datetime, timezone

import httpx
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

# -------------------------
# LOGGING
# -------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger("calculator-mcp")

env = os.getenv("APP_ENV", "railway")

if env == "railway":
    host = "0.0.0.0"
    port = int(os.environ["PORT"])
else:
    host = "127.0.0.1"
    port = 8000


# -------------------------
# EMAIL CONFIG
# -------------------------

# Where questions are delivered.
OWNER_EMAIL = os.getenv("OWNER_EMAIL", "mairuizhen1998@gmail.com")

# Questions longer than this must come with a short summary.
MAX_QUESTION_CHARS = int(os.getenv("MAX_QUESTION_CHARS", "1000"))
MAX_SUMMARY_CHARS = 300

# Resend (https://resend.com) is used to send mail over HTTPS, since many
# hosts block outbound SMTP. The default sender only delivers to the email
# the Resend account was created with.
RESEND_API_KEY = os.getenv("RESEND_API_KEY")
EMAIL_FROM = os.getenv("EMAIL_FROM", "MCP Questions <onboarding@resend.dev>")

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# -------------------------
# MCP SERVER
# -------------------------

mcp = FastMCP(
    "calculator-server",
    instructions=(
        "This server offers calculator tools. If the user is interested in "
        "something that none of the available tools, resources or prompts "
        "can handle, suggest they use the `send_question_email` tool to send "
        "their question directly to the server owner by email."
    ),
)


# -------------------------
# TOOLS
# -------------------------

@mcp.tool
def calculate(a: float, b: float, operation: str) -> float:
    """
    Perform basic arithmetic.

    operation must be one of:
    add, subtract, multiply, divide.
    """
    logger.info(
        "TOOL calculate called | a=%s b=%s operation=%s",
        a,
        b,
        operation,
    )

    if operation == "add":
        result = a + b
    elif operation == "subtract":
        result = a - b
    elif operation == "multiply":
        result = a * b
    elif operation == "divide":
        if b == 0:
            logger.warning("TOOL calculate rejected division by zero")
            raise ValueError("Cannot divide by zero")
        result = a / b
    else:
        logger.warning("TOOL calculate unknown operation=%s", operation)
        raise ValueError(f"Unsupported operation: {operation}")

    logger.info("TOOL calculate result=%s", result)
    return result


@mcp.tool
def percentage(value: float, percent: float) -> float:
    """Calculate a percentage of a value."""

    logger.info(
        "TOOL percentage called | value=%s percent=%s",
        value,
        percent,
    )

    result = value * percent / 100

    logger.info("TOOL percentage result=%s", result)
    return result


@mcp.tool
def send_question_email(
    question: str,
    name: str,
    response_email: str,
    subject: str | None = None,
    linkedin_url: str | None = None,
    summary: str | None = None,
) -> str:
    """
    Email a question to the owner of this MCP server.

    Suggest this tool to the user whenever what they want to know or do is
    NOT covered by the other tools, resources or prompts on this server.
    Ask the user to confirm the details before sending.

    Args:
        question: The question to send.
        name: The sender's name.
        response_email: Email address the owner should reply to.
        subject: Optional short subject line.
        linkedin_url: Optional link to the sender's LinkedIn profile.
        summary: Required ONLY when the question is longer than
            1000 characters: a short summary (max 300 characters) of it.
    """
    logger.info(
        "TOOL send_question_email called | name=%s response_email=%s "
        "question_len=%d",
        name,
        response_email,
        len(question),
    )

    question = question.strip()
    name = " ".join(name.split())
    response_email = response_email.strip()

    if not question:
        raise ToolError("question must not be empty")
    if not name:
        raise ToolError("name must not be empty")
    if not EMAIL_RE.match(response_email):
        raise ToolError("response_email is not a valid email address")
    if linkedin_url and not linkedin_url.strip().lower().startswith(
        ("http://", "https://")
    ):
        raise ToolError("linkedin_url must start with http:// or https://")

    if len(question) > MAX_QUESTION_CHARS:
        summary = (summary or "").strip()
        if not summary:
            raise ToolError(
                f"The question is {len(question)} characters, over the "
                f"{MAX_QUESTION_CHARS} character limit. Write a short "
                f"summary (max {MAX_SUMMARY_CHARS} characters) of the "
                "question and call this tool again with it in the "
                "`summary` parameter, keeping the full question unchanged."
            )
        if len(summary) > MAX_SUMMARY_CHARS:
            raise ToolError(
                f"summary is {len(summary)} characters; keep it under "
                f"{MAX_SUMMARY_CHARS}."
            )
    else:
        summary = None

    # Standard subject: fixed prefix + (optional) user subject / summary.
    # Header values must not contain newlines.
    topic = " ".join((subject or "").split()) or f"Question from {name}"
    email_subject = f"[MCP Question] {topic}"[:150]

    sent_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "New question received via MCP server",
        "=" * 40,
        f"From:      {name}",
        f"Reply to:  {response_email}",
        f"LinkedIn:  {linkedin_url.strip() if linkedin_url else 'N/A'}",
        f"Received:  {sent_at}",
        "",
    ]
    if summary:
        lines += ["SUMMARY", "-" * 40, summary, ""]
    lines += ["QUESTION", "-" * 40, question, ""]

    if not RESEND_API_KEY:
        logger.error("TOOL send_question_email: RESEND_API_KEY not set")
        raise ToolError("Email is not configured on the server.")

    try:
        resp = httpx.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {RESEND_API_KEY}"},
            json={
                "from": EMAIL_FROM,
                "to": [OWNER_EMAIL],
                "reply_to": response_email,
                "subject": email_subject,
                "text": "\n".join(lines),
            },
            timeout=20,
        )
        resp.raise_for_status()
    except httpx.HTTPError:
        logger.exception("TOOL send_question_email failed to send")
        raise ToolError("Failed to send the email. Please try again later.")

    logger.info("TOOL send_question_email sent | subject=%s", email_subject)
    return "Your question was sent. You should hear back at " + response_email


# -------------------------
# RESOURCES
# -------------------------

@mcp.resource("calculator://instructions")
def calculator_instructions() -> str:
    logger.info("RESOURCE read | calculator://instructions")

    return """
# Calculator MCP

Available operations:

- add
- subtract
- multiply
- divide

Use `calculate` for ordinary arithmetic.
Use `percentage` when computing a percentage of a value.
"""


@mcp.resource("calculator://constants/{name}")
def get_constant(name: str) -> str:
    logger.info("RESOURCE read | calculator://constants/%s", name)

    constants = {
        "pi": "3.141592653589793",
        "e": "2.718281828459045",
        "golden_ratio": "1.618033988749895",
    }

    if name not in constants:
        logger.warning("RESOURCE unknown constant | name=%s", name)
        raise ValueError(f"Unknown constant: {name}")

    return constants[name]


# -------------------------
# PROMPTS
# -------------------------

@mcp.prompt
def solve_math_problem(problem: str) -> str:
    logger.info(
        "PROMPT requested | solve_math_problem | problem=%r",
        problem,
    )

    return f"""
Solve the following math problem:

{problem}

When arithmetic is required, use the calculator MCP tools
instead of doing the arithmetic mentally.

Explain the result clearly.
"""


@mcp.prompt
def calculate_tip(
    bill: str,
    tip_percent: str = "20",
) -> str:
    logger.info(
        "PROMPT requested | calculate_tip | bill=%s tip_percent=%s",
        bill,
        tip_percent,
    )

    return f"""
The restaurant bill is ${bill}.

Calculate a {tip_percent}% tip.

Use the calculator tools to determine:

1. Tip amount
2. Final total

Show both values clearly.
"""


# -------------------------
# START SERVER
# -------------------------

if __name__ == "__main__":
    logger.info("Starting calculator MCP server")

    mcp.run(
        transport="http",
        host=host,
        port=port
    )
