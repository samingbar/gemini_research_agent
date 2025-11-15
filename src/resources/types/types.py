from pydantic import BaseModel, model_validator
from enum import Enum
from typing import Optional, Dict, Any, List, Type, Literal, Union

MessageRole = Literal[
    "system",
    "user",
    "assistant",
    "tool-call",
    "tool-response",
]

class LLMMessage(BaseModel):
    role: MessageRole
    content: Union[str, Dict[str, Any]]
    tool_name: Optional[str] = None
    tool_call_id: Optional[str] = None

    # -------------------------------------
    # Post-validation: enforce correct shape
    # -------------------------------------
    @model_validator(mode="after")
    def validate_role_content(self):
        # SYSTEM / USER / ASSISTANT → content must be STRING
        if self.role in ("system", "user", "assistant"):
            if not isinstance(self.content, str):
                raise ValueError(
                    f"Message with role '{self.role}' must have string content"
                )
            # No tool metadata on assistant/system messages
            self.tool_name = None
            self.tool_call_id = None

        # TOOL-CALL → must be dict
        if self.role == "tool-call":
            if not isinstance(self.content, dict):
                raise ValueError("tool-call messages must use dict content")
            # Remove irrelevant fields
            self.tool_call_id = None  # Only responses have ID

        # TOOL-RESPONSE → must be dict
        if self.role == "tool-response":
            if not isinstance(self.content, dict):
                raise ValueError("tool-response messages must use dict content")
            # tool-response may have a name + id (workflow internal)
            # Gemini activity will convert this to a function_response part

        return self

    # -------------------------------------
    # Normalization for serialization
    # -------------------------------------
    def model_dump(self, *args, **kwargs):
        d = super().model_dump(*args, **kwargs)
        # Do not leak to Gemini/OpenAI directly — activity will convert
        return d

class ToolArgs(BaseModel):
    name: str
    arguments: Dict[str, Any]

class GeminiFinal(BaseModel):
    type: str = "final"
    answer: str

class GeminiToolCalls(BaseModel):
    type: str = "tool_calls"
    calls: List[ToolArgs]

class AgentInput(BaseModel):
    query: str
    max_steps: int = 8

class AgentOutput(BaseModel):
    answer: str
    plan: str
    steps: int
    tools_used: List[str]

class GeminiActivityInput(BaseModel):
    messages: List[LLMMessage]  # Pydantic BaseModels
    tools_schema: List[Dict[str, Any]]

class ToolName(str, Enum):
    VALIDATE_COMPANY = "validate_company"
    IDENTIFY_SECTOR = "identify_sector"
    IDENTIFY_COMPETITORS = "identify_competitors"
    BROWSE_PAGE = "browse_page"
    GENERATE_REPORT = "generate_report"

class ValidateCompanyArgs(BaseModel):
    company_name: str


class IdentifySectorArgs(BaseModel):
    company_name: str


class IdentifyCompetitorsArgs(BaseModel):
    sector: str
    company_name: str


class BrowsePageArgs(BaseModel):
    url: str
    instructions: str


class GenerateReportArgs(BaseModel):
    company_name: str
    context: str


class ToolRegistry(BaseModel):
    tools: Dict[ToolName, Type[BaseModel]]

    def gemini_tool_schema(self):
        schema_list = []
        for name, model in self.tools.items():
            schema_list.append({
                "function_declarations": [
                    {
                        "name": name.value,
                        "parameters": model.model_json_schema()
                    }
                ]
            })
        return schema_list

    def parse_tool_call(self, fc: Dict[str, Any]):
        """
        Gemini-native function call structure:
        fc = {
            "name": "validate_company",
            "args": {"company_name": "Temporal"}
        }
        """
        tool_name = ToolName(fc["name"])
        args_model = self.tools[tool_name]
        return tool_name, args_model(**fc["args"])