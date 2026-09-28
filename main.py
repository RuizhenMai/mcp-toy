import logging
from fastmcp import FastMCP
import os

# -------------------------
# LOGGING
# -------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger("calculator-mcp")


# -------------------------
# MCP SERVER
# -------------------------

mcp = FastMCP("calculator-server")


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
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8000)),
    )
