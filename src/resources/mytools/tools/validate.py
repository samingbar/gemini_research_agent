from pydantic import BaseModel
from ..decorators import tool

class CompanyRequest(BaseModel):
    company_name: str

@tool
def validate_company(req: CompanyRequest) -> str:
    """Validate that a company exists."""
    print("[TOOL] validate_company")
    return f"Validated: {req.company_name}"
