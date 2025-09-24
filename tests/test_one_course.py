import json
import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app.validator import validate_text
from cli.syllabus_validate import build_text   # ← 普通のと同じ build_text を利用

# JSONファイルをロード
with open("data/syllabus_2025_full.llm.json", "r", encoding="utf-8") as f:
    data = json.load(f)

# 任意の件を取り出す（例: 2件目 = index 1）
course = data[47]

# cli版と同じbuild_textでテキストを作る
sample_text = course.get("text") or build_text(course)

# validator.py の関数を実行
result = validate_text(
    sample_text,
    use_llm=True,
    provider="ollama",
    model="elyza:8b-q8"
)

print(json.dumps(result, ensure_ascii=False, indent=2))
