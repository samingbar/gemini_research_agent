from ..decorators import tool
from pydantic import BaseModel
from typing import List, Union, Any

class ReportRequest(BaseModel):
    company_name: str
    context: List[Union[str, Any]]

@tool
def generate_report(input: ReportRequest) -> str:
    """Generate competitive analysis report."""
    print("[TOOL] generate_report")
    return f"# Report for {input.company_name}\n\n{input.context}"
