import json
import re
import html
from urllib.request import urlopen

from google import genai

from .mytools.decorators import tool
from .custom_types.types import (
    ValidateCompanyArgs,
    IdentifySectorArgs,
    IdentifyCompetitorsArgs,
    BrowsePageArgs,
    GenerateReportArgs,
)

client = genai.Client()

def _normalize_company_name(name: str) -> str:
    return re.sub(r"\s+", " ", name or "").strip()


def _call_gemini_json(prompt: str) -> str:
    """
    Helper to call Gemini with a JSON-only response contract.
    Returns the raw JSON string from the first candidate.
    """
    config = genai.types.GenerateContentConfig(
        response_mime_type="application/json",
    )
    resp = client.models.generate_content(
        model="gemini-2.5-pro",
        contents=prompt,
        config=config,
    )
    msg = resp.candidates[0].content
    part = msg.parts[0]
    txt = getattr(part, "text", None)
    if txt is None:
        txt = str(part)
    return txt


@tool
def validate_company(args: ValidateCompanyArgs) -> str:
    """
    Validate if the input company name corresponds to a real, recognized company.

    Behavior:
    - Relies on the LLM's internal knowledge of real-world companies.
    - Does not use a hard-coded company list.
    - Returns structured JSON with:
      - is_valid: boolean
      - normalized_name: cleaned-up company name (or null)
      - confidence: 0–1 float
      - reason: short explanation
    - The agent should treat is_valid=False as a hard signal to stop further analysis.

    This tool is intended to be called at most once per distinct company_name
    unless new information suggests the earlier result is wrong.
    """
    print("[TOOL] validate_company")
    candidate = _normalize_company_name(args.company_name or "")
    prompt = f"""
You are an expert in business and industry knowledge.

Task: Determine whether the following company name refers to a real, recognized company.

Company: "{candidate}"

Respond with a single JSON object with fields:
- "is_valid": boolean
- "normalized_name": string or null
- "confidence": number between 0 and 1
- "reason": short string explanation

Do not include any text before or after the JSON.
"""
    return _call_gemini_json(prompt)


@tool
def identify_sector(args: IdentifySectorArgs) -> str:
    """
    Determine the primary industry sector of the given company.

    Behavior:
    - Relies on the LLM's knowledge of industries and companies.
    - Returns structured JSON with:
      - sector: short sector label
      - confidence: 0–1 float
      - reason: why this sector was chosen
    """
    print("[TOOL] identify_sector")
    candidate = _normalize_company_name(args.company_name or "")
    prompt = f"""
You are an expert in business and industry classification.

Task: Identify the primary industry sector for the following company.

Company: "{candidate}"

Respond with a single JSON object with fields:
- "sector": short sector label, such as "Technology", "EdTech", "Finance", etc.
- "confidence": number between 0 and 1
- "reason": short explanation of why this sector was chosen

If you genuinely cannot determine a sector, use "Unknown sector" with low confidence.

Do not include any text before or after the JSON.
"""
    return _call_gemini_json(prompt)


@tool
def identify_competitors(args: IdentifyCompetitorsArgs) -> str:
    """
    Identify the top competitors in the given sector, excluding the input company.

    Behavior:
    - Relies on the LLM's knowledge of the market.
    - Always excludes the focal company if it appears in the list.
    - Returns structured JSON with:
      - competitors: list of competitor names (up to 3)
      - sector: sector used for lookup
      - reason: explanation
    """
    print("[TOOL] identify_competitors")

    company = _normalize_company_name(args.company_name or "")
    sector = (args.sector or "").strip()

    prompt = f"""
You are an expert in market and competitive analysis.

Task: Identify the top competitors for a company within a sector.

Company: "{company}"
Sector context (may be empty): "{sector}"

Respond with a single JSON object with fields:
- "competitors": array of competitor company names (up to 3), excluding the focal company.
- "sector": sector you used for your reasoning (may refine or correct the input sector).
- "reason": short explanation of why these companies were chosen.

Focus on real-world, meaningful competitors. If you cannot identify any, return an empty array
and explain why in the reason.

Do not include any text before or after the JSON.
"""
    return _call_gemini_json(prompt)


def _strip_html(text: str) -> str:
    # Remove HTML tags and collapse whitespace.
    no_tags = re.sub(r"<[^>]+>", " ", text)
    unescaped = html.unescape(no_tags)
    return re.sub(r"\s+", " ", unescaped).strip()


@tool
def browse_page(args: BrowsePageArgs) -> str:
    """
    Browse a webpage and extract information based on instructions.

    Behavior:
    - Performs a simple HTTP GET for the given URL.
    - Strips HTML tags and returns the first few kilobytes of visible text.
    - Does not execute JavaScript or handle complex layouts.
    - Returns structured JSON with:
      - url: the requested URL
      - snippet: extracted text snippet
      - instructions: echoed instructions for grounding
      - note: limitations or errors, if any
    """
    print("[TOOL] browse_page")
    url = args.url
    instructions = args.instructions or ""

    snippet = ""
    note = ""

    try:
        with urlopen(url, timeout=10) as resp:
            raw = resp.read()
            try:
                html_text = raw.decode("utf-8", errors="ignore")
            except Exception:
                html_text = raw.decode(errors="ignore")
            cleaned = _strip_html(html_text)
            # Limit length to keep responses manageable.
            snippet = cleaned[:4000]
    except Exception as exc:
        note = f"Failed to fetch URL: {exc}"

    result = {
        "url": url,
        "snippet": snippet,
        "instructions": instructions,
        "note": note or "Content fetched successfully; snippet may be truncated.",
    }
    return json.dumps(result)


@tool
def generate_report(args: GenerateReportArgs) -> str:
    """
    Generate a competitive analysis report with a comparison table and actionable insights.

    Behavior:
    - Uses the provided context (facts, tool outputs, prior reasoning) as raw material.
    - Produces a Markdown report with sections:
      - Executive Summary
      - Comparison Table
      - Actionable Insights for the company
    - The FINAL ANSWER marker is applied at the workflow / model level;
      this tool focuses on structuring the content.

    Input expectations:
    - company_name: focal company for the analysis.
    - context: textual or JSON-structured context assembled by the agent.
    """
    print("[TOOL] generate_report")

    company = _normalize_company_name(args.company_name)
    context_text = args.context or ""

    header = f"# Competitive Analysis Report: {company}\n"

    executive_summary = (
        "## Executive Summary\n\n"
        "This report summarizes the competitive landscape for the company above, "
        "highlighting key competitors, strategic themes, and areas of opportunity.\n\n"
    )

    comparison_table = (
        "## Comparison Table\n\n"
        "| Competitor | Strategy Type | Key Tactics | Strengths | Weaknesses |\n"
        "|-----------|---------------|-------------|-----------|------------|\n"
        "| (fill)    | (fill)        | (fill)      | (fill)    | (fill)     |\n\n"
        "_The agent should refine this table using the latest tool outputs and reasoning in context._\n\n"
    )

    insights = (
        "## Actionable Insights\n\n"
        f"- Identify 3–5 high-impact initiatives {company} can take based on the latest context.\n"
        "- Focus on differentiation vs. the strongest competitors.\n"
        "- Consider product, pricing, distribution, brand, and innovation levers.\n\n"
    )

    context_section = (
        "## Source Context\n\n"
        "The following raw context was used to inform this report:\n\n"
        "```text\n"
        f"{context_text}\n"
        "```\n"
    )

    return header + "\n" + executive_summary + comparison_table + insights + context_section
