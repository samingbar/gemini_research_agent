from pydantic import BaseModel
from ..decorators import tool

class CompetitorRequest(BaseModel):
    sector: str
    company_name: str

@tool
def identify_competitors(req: CompetitorRequest) -> str:
    """Identify competitors."""
    print("[TOOL] identify_competitors")
    return "Meta, Amazon, Microsoft"
