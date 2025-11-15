import inspect
import typing
import io
import textwrap
import base64

from typing import Any, Dict
from temporalio import activity
from google import genai

from pydantic import BaseModel
from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas

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

    config = genai.types.GenerateContentConfig(
        tools=TOOL_SCHEMAS,
    )

    resp = client.models.generate_content(
        model="gemini-2.5-pro",
        contents=contents,
        config=config,
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

    # Otherwise plain text; decide if this is truly final
    txt = getattr(part, "text", None)
    if txt is None:
        txt = str(part)

    normalized = txt.strip().lower()
    # Treat as final only if the model explicitly marks it as such.
    is_final = normalized.startswith("final answer:") or normalized.startswith("final answer")

    return AgentStepOutput(
        is_final=is_final,
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


@activity.defn
async def render_report_pdf(markdown_report: str) -> str:
    """
    Render a Markdown report into a simple, nicely formatted PDF.

    Returns:
        Base64-encoded PDF bytes as a UTF-8 string.
    """
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=LETTER)
    width, height = LETTER

    # Simple layout: title + body text with wrapping
    margin_x = 72  # 1 inch
    margin_top = height - 72
    line_height = 14

    lines = markdown_report.splitlines()

    y = margin_top

    for raw_line in lines:
        line = raw_line.rstrip()

        # Interpret H1 headings as larger bold text
        if line.startswith("# "):
            text = line[2:].strip()
            c.setFont("Helvetica-Bold", 18)
            c.drawString(margin_x, y, text)
            y -= line_height * 2
            continue
        elif line.startswith("## "):
            text = line[3:].strip()
            c.setFont("Helvetica-Bold", 14)
            c.drawString(margin_x, y, text)
            y -= line_height * 1.5
            continue
        elif line.startswith("### "):
            text = line[4:].strip()
            c.setFont("Helvetica-Bold", 12)
            c.drawString(margin_x, y, text)
            y -= line_height * 1.3
            continue

        # Normal paragraph text; wrap to page width
        if not line.strip():
            y -= line_height
            continue

        c.setFont("Helvetica", 11)
        max_width = width - 2 * margin_x

        wrapped = textwrap.wrap(line, width=90)
        for wline in wrapped:
            if y <= 72:
                c.showPage()
                y = margin_top
                c.setFont("Helvetica", 11)
            c.drawString(margin_x, y, wline)
            y -= line_height

    c.showPage()
    c.save()

    pdf_bytes = buffer.getvalue()
    buffer.close()

    # Return as base64 so it is easy to store / transmit
    return base64.b64encode(pdf_bytes).decode("utf-8")
