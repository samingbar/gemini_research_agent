from ..decorators import tool
from pydantic import BaseModel
from typing import List, Union, Any


class ReportRequest(BaseModel):
    company_name: str
    context: List[Union[str, Any]]


def generate_report(input: ReportRequest) -> str:
    """Legacy generate_report tool (not registered with Gemini)."""
    print("[TOOL] generate_report (legacy)")
    return f"# Report for {input.company_name}\n\n{input.context}"
