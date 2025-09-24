
# API仕様
## POST /validate/text
- Request: `{ "text": string, "use_llm": boolean, "provider": "openai|ollama|none", "model": string|null, "min_weeks": number }`
- Response:
```json
{
  "result": {
    "evaluations": [
      {"raw_name":"小テスト","percent":20.0,"normalized_candidate":"Quiz","normalized_final":"Quiz"}
    ],
    "evaluation_total_percent": 100.0,
    "evaluation_total_is_100": true,
    "evaluation_by_normalized_name": {"Quiz":20.0, "Exam":30.0, "Participation":50.0},
    "detected_week_count": 14,
    "week_markers": ["第1回","..."],
    "llm_notes": []
  },
  "alerts": [{"type":"warn","message":"週次計画が14週に満たない可能性（検出 0 週）。"}]
}
```
## POST /validate/batch
- Request: `{ "items": [ValidateTextRequest, ...] }`
- Response: `{ "results": [ValidateResponse, ...] }`
