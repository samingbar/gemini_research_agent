from .registry import register_tool, TOOL_REGISTRY, DISPATCH_TABLE
from .schemas import build_gemini_schema

# Ensure tool modules are imported so decorators run and
# TOOL_REGISTRY / DISPATCH_TABLE are populated.
from . import tools as _tools  # noqa: F401
from .. import company_research_tools as _company_tools  # noqa: F401

# Backwards-compatible aliases used by workflow activities
TOOL_DISPATCH = DISPATCH_TABLE
TOOL_SCHEMAS = [build_gemini_schema()]
