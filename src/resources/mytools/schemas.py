from .registry import TOOL_REGISTRY

def build_gemini_schema():
    return {
        "function_declarations": TOOL_REGISTRY
    }
