from pydantic import BaseModel


class CompetitorRequest(BaseModel):
    sector: str
    company_name: str


def identify_competitors(req: CompetitorRequest) -> str:
    """Legacy identify_competitors tool (not registered with Gemini)."""
    print("[TOOL] identify_competitors (legacy)")
    return "Meta, Amazon, Microsoft"
