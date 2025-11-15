from ..decorators import tool

@tool
def browse_page(url: str, instructions: str) -> str:
    """Fetch data from a webpage."""
    print("[TOOL] browse_page")
    return f"Summary of {url} with: {instructions}"
