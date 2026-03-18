"""
Prompt injection detection heuristics.
Detects known attack patterns: instruction override, role hijacking, jailbreaks.
"""
import re
from dataclasses import dataclass
from typing import Pattern


@dataclass(frozen=True)
class InjectionPattern:
    name: str
    pattern: Pattern[str]


INJECTION_PATTERNS: list[InjectionPattern] = [
    InjectionPattern("IGNORE_INSTRUCTIONS",   re.compile(r'(?i)ignore\s+(all\s+)?(previous|prior|above|earlier)\s+instructions?')),
    InjectionPattern("DISREGARD_PROMPT",      re.compile(r'(?i)(disregard|forget|override|bypass)\s+(your\s+)?(system\s+)?(prompt|instructions?|rules?|guidelines?)')),
    InjectionPattern("NEW_INSTRUCTIONS",      re.compile(r'(?i)your\s+(new|real|actual|true)\s+instructions?\s+(are|is)\s*:')),
    InjectionPattern("ROLE_HIJACK",           re.compile(r'(?i)(you\s+are\s+now|act\s+as|pretend\s+(to\s+be|you\s+are)|roleplay\s+as)\s+(an?\s+)?(evil|uncensored|unfiltered|DAN|jailbreak)')),
    InjectionPattern("DAN_JAILBREAK",         re.compile(r'(?i)\bDAN\b.*\b(mode|enabled|activated|jailbreak)\b')),
    InjectionPattern("SYSTEM_PROMPT_LEAK",    re.compile(r'(?i)(print|repeat|reveal|show|output|tell me|what is)\s+(your\s+)?(system\s+prompt|initial\s+instructions?|original\s+prompt)')),
    InjectionPattern("CONTEXT_ESCAPE",        re.compile(r'(?i)(</?(system|user|assistant|instruction)>|\[INST\]|\[/INST\]|<\|im_start\|>|<\|im_end\|>)')),
    InjectionPattern("TRANSLATOR_TRICK",      re.compile(r'(?i)translate\s+.{0,30}\s+and\s+(instead|actually|really)\s+(say|respond|output)')),
]


def find_injections(text: str) -> list[str]:
    """Return list of matched injection pattern names found in text."""
    found = []
    for ip in INJECTION_PATTERNS:
        if ip.pattern.search(text):
            found.append(ip.name)
    return found
