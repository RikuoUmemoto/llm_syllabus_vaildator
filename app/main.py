from fastapi import FastAPI
from app.schema import ValidateTextRequest, ValidateResponse, ValidateBatchRequest
from app.validator import validate_text
import os

app = FastAPI(title="LLM活用型シラバス検証API", version="0.1.0")

# 例: app/assets/normalize_rules.yaml に置いている前提
RULES_PATH = os.path.join(os.path.dirname(__file__), "assets", "normalize_rules.yaml")

@app.post("/validate/text", response_model=ValidateResponse)
def validate_text_endpoint(req: ValidateTextRequest):
    """
    ※ validator.validate_text は純LLM版（use_llm 引数なし）
       スキーマに use_llm が残っていてもここでは使わない（無視）。
    """
    data = validate_text(
        text=req.text,
        provider=(req.provider or "ollama"),
        model=(req.model or "elyza:8b-q8"),
        min_weeks=(req.min_weeks or 14),
        rules_yaml_path=RULES_PATH,
    )
    return data

@app.post("/validate/batch")
def validate_batch_endpoint(req: ValidateBatchRequest):
    """
    バッチ版も同様に use_llm を使わず呼び出す。
    """
    out = []
    for item in req.items:
        out.append(
            validate_text(
                text=item.text,
                provider=(item.provider or "ollama"),
                model=(item.model or "elyza:8b-q8"),
                min_weeks=(item.min_weeks or 14),
                rules_yaml_path=RULES_PATH,
            )
        )
    return {"results": out}
