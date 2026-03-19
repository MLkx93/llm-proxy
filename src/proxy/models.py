from pydantic import BaseModel
from typing import Optional, List, Literal


class Message(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class ChatCompletionRequest(BaseModel):
    model: str
    messages: List[Message]
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    # stream is intentionally excluded — streaming is blocked in v1


class ErrorDetail(BaseModel):
    code: str
    message: str
    request_id: str


class ErrorResponse(BaseModel):
    error: ErrorDetail


# --- Anthropic-format error models ---

class AnthropicErrorDetail(BaseModel):
    type: str          # e.g. "invalid_request_error", "authentication_error"
    message: str


class AnthropicErrorResponse(BaseModel):
    type: str = "error"
    error: AnthropicErrorDetail
