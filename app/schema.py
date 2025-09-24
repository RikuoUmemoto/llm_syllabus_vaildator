
from pydantic import BaseModel, Field
from typing import List, Optional, Literal, Dict, Any

Provider = Literal["openai","ollama","none"]

class ValidateTextRequest(BaseModel):
    text: str = Field(..., description="抽出対象のシラバステキスト（単一）")
    use_llm: bool = Field(False, description="LLMを使うか（デフォルトFalse=ルールのみ）")
    provider: Provider = "none"
    model: Optional[str] = None
    min_weeks: int = 14

class EvaluationComponent(BaseModel):
    raw_name: str
    percent: float
    normalized_candidate: Optional[str] = None
    normalized_final: str

class ValidateResult(BaseModel):
    evaluations: List[EvaluationComponent] = []
    evaluation_total_percent: float
    evaluation_total_is_100: bool
    evaluation_by_normalized_name: Dict[str, float]
    detected_week_count: int
    week_markers: List[str] = []
    llm_notes: List[str] = []

class ValidateResponse(BaseModel):
    result: ValidateResult
    alerts: List[Dict[str, Any]] = []

class ValidateBatchRequest(BaseModel):
    items: List[ValidateTextRequest]
