def browse_page(url: str, instructions: str) -> str:
    """Legacy browse_page tool (not registered with Gemini)."""
    print("[TOOL] browse_page (legacy)")
    return f"Summary of {url} with: {instructions}"
