# Lessons Learned

| Date | What Went Wrong | Rule to Prevent It |
|------|----------------|-------------------|
| 2026-03-18 | Session started without tasks/ directory existing | Always bootstrap tasks/lessons.md and tasks/todo.md at session start if missing |
| 2026-03-18 | Missing deps in requirements.txt (presidio, spacy, PyYAML) — Docker worked but local dev broke | Every import must have a matching entry in requirements.txt. Verify with fresh venv install. |
| 2026-03-18 | Missing src/__init__.py broke Python package imports | Always create __init__.py when adding new package directories |
| 2026-03-19 | System Python is externally managed — pip install fails outside venv | Always use .venv/bin/python and .venv/bin/pip, never system python3 |
| 2026-03-19 | settings import was local to ready() function, not available in chat_completions() | Put shared imports at module level, not inside individual functions |
| 2026-03-19 | .env changes not picked up by running uvicorn --reload | --reload only watches code files, not .env. Must restart server manually after .env changes |
| 2026-03-19 | LITELLM_API_BASE was missing /api suffix — upstream returned 404 | Always verify the exact base URL by testing directly with curl before configuring the proxy |
| 2026-03-19 | Assumed LiteLLM server exposes /v1/messages (Anthropic endpoint) — it only had /v1/chat/completions (OpenAI) | Never assume upstream API shape. Probe with curl /v1/models first, then check available routes |
| 2026-03-19 | Tests mocked Anthropic-format upstream responses but code now translates from OpenAI format | When changing the forwarding mechanism, update test mocks to match the new upstream response format |
| 2026-03-19 | Built separate proxy auth (api_keys.yaml) when users already have LiteLLM keys | Ask about auth model early — don't add complexity users don't need. Pass-through auth when the upstream already handles it. |
| 2026-03-19 | Trailing space in .env LITELLM_API_KEY caused "Invalid API key" — invisible but fatal | Always strip whitespace from .env values. Add .env format validation or trim keys in settings.py at load time. |
| 2026-03-19 | Claude Code sends Authorization: Bearer (not x-api-key) — proxy rejected it | Accept both x-api-key and Authorization: Bearer headers on the Anthropic endpoint |
| 2026-03-19 | Presidio flagged PERSON and URL in Claude Code's system prompt — false positive blocking all requests | Only scan user messages, not system prompts or assistant messages. System prompts are tool-generated and full of URLs/names. |

