import inspect
import typing

from typing import Any, Dict
from temporalio import activity
from google import genai

from pydantic import BaseModel

from ...resources.mytools import TOOL_DISPATCH, TOOL_SCHEMAS
from ...resources.custom_types.types import AgentStepInput, AgentStepOutput, ToolCall


client = genai.Client()


@activity.defn
async def llm_step_activity(step: AgentStepInput) -> AgentStepOutput:
    """
    Call Gemini with:
      - prior message history (already assembled)
      - the original task text
    Return either:
      - a final answer, or
      - a tool call request
    """

    contents = step.history

    resp = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=contents,
    )

    msg = resp.candidates[0].content

    # Parse first part for a potential function call
    part = msg.parts[0]
    func_call = getattr(part, "function_call", None)

    if func_call:
        return AgentStepOutput(
            is_final=False,
            tool_call=ToolCall(name=func_call.name, arguments=dict(func_call.args)),
            model_message={"role": getattr(msg, "role", None)},
        )

    # Otherwise plain text
    txt = getattr(part, "text", None)
    if txt is None:
        txt = str(part)

    return AgentStepOutput(
        is_final=True,
        output_text=txt,
        model_message={"role": getattr(msg, "role", None)},
    )


def _invoke_tool(fn, args: Dict[str, Any]) -> Any:
    """
    Invoke a registered tool function, supporting either:
    - A single Pydantic model argument
    - Standard kwargs
    """
    sig = inspect.signature(fn)
    params = list(sig.parameters.values())

    if len(params) == 1:
        param = params[0]
        hints = typing.get_type_hints(fn)  # type: ignore[name-defined]
        annotation = hints.get(param.name)

        if isinstance(annotation, type) and issubclass(annotation, BaseModel):
            model_cls = annotation
            return fn(model_cls(**args))

    return fn(**args)


@activity.defn
async def tool_activity(tool_call: ToolCall) -> str:
    """
    Run the Python tool from TOOL_DISPATCH.
    """
    tool_fn = TOOL_DISPATCH[tool_call.name]
    result = _invoke_tool(tool_fn, tool_call.arguments)

    # Convert to text for Gemini consumption
    return str(result)
