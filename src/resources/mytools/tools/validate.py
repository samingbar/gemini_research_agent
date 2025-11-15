from pydantic import BaseModel


class CompanyRequest(BaseModel):
    company_name: str


def validate_company(req: CompanyRequest) -> str:
    """Legacy validate_company tool (not registered with Gemini)."""
    print("[TOOL] validate_company (legacy)")
    return f"Validated: {req.company_name}"
