from pydantic import BaseModel, Field
from typing import Optional, List, Literal, Union, Any


class Message(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: Union[str, List[Any]]


class ChatCompletionRequest(BaseModel):
    model: str
    messages: List[Message]
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    stream: Optional[bool] = False


class AnthropicMessageRequest(BaseModel):
    """Pydantic model for Anthropic /v1/messages endpoint."""
    model: str
    messages: List[Message]
    max_tokens: int = Field(..., description="Maximum number of tokens to generate")
    temperature: Optional[float] = Field(0.7, ge=0.0, le=2.0)
    stream: Optional[bool] = False
    system: Optional[str] = None


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
