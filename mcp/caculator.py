from mcp.server.fastmcp import FastMCP
import logging
import os

mcp = FastMCP("caculator")

logging.basicConfig(
    filename=os.path.join(os.path.dirname(__file__), "caculator.log"),
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    encoding="utf-8"
)

logger = logging.getLogger(__name__)

@mcp.tool()
async def caculator(express: str) -> str:
    """Calculate the result of a math expression.

    Args:
        express: Math expression to evaluate (e.g., "2+3*4")
    """
    try:
        result = eval(express)
        logger.info(f"expression result: {result}")
        return str(result)
    except Exception as e:
        logger.error(f"expression error result: {e}")
        return f"Error: {e}"


if __name__ == "__main__":
    mcp.run(transport="stdio")
