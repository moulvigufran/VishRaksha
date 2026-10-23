"""Optional: read the 108 call note with Claude instead of rules.

Set ANTHROPIC_API_KEY (pip install anthropic) and run with --llm.
The output has the same fields as tools.parse_call_note, so the agent
loop does not change. If the call fails, we fall back to the rule parser.
"""
import json

from . import tools
from .data import VILLAGES

SCHEMA = {
    "type": "object",
    "properties": {
        "is_snakebite": {"type": "boolean"},
        "village_text": {"type": ["string", "null"]},
        "village_confidence": {"type": "number"},
        "minutes_since_bite": {"type": ["integer", "null"]},
        "caller_phone": {"type": ["string", "null"]},
    },
    "required": ["is_snakebite", "village_text", "village_confidence", "minutes_since_bite", "caller_phone"],
    "additionalProperties": False,
}


def parse_call_note_llm(text: str) -> dict:
    try:
        import anthropic
        client = anthropic.Anthropic()
        response = client.beta.messages.create(
            model="claude-opus-5-5",
            max_tokens=2000,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            output_config={"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}},
            system=("You read emergency call notes written by 108 call-takers in Hindi, English or Hinglish. "
                    "Extract facts only. Do not give medical advice. village_text must be one of: "
                    + ", ".join(v.name for v in VILLAGES)
                    + " or null. village_confidence is 0-1: how sure you are about the village."),
            messages=[{"role": "user", "content": text}],
        )
        if response.stop_reason == "refusal":
            raise RuntimeError("refused")
        block = next(b for b in response.content if b.type == "text")
        return json.loads(block.text)
    except Exception as e:  # any failure -> rules, so the emergency flow never stops
        print(f"(LLM parser unavailable: {e.__class__.__name__}; using rule parser)")
        return tools.parse_call_note(text)
