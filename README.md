
# LLM活用型シラバス検証システム（14週基準）
**目的**: 大学シラバスから *評価割合* と *週次計画* を抽出・正規化し、**評価合計=100%** と **授業週≥14** を検証。LLMで曖昧表現（「3割」「半分」等）を数値化。
- 研究発表/PoC/学内稟議にそのまま使える **API・CLI・テスト・ドキュメント** を含みます。
- デフォルトで「授業週=14週」を正とします（`MIN_WEEKS=14`）。

## 使い方（クイック）
```bash
# 1) 依存関係
pip install -r requirements.txt

# 2) API起動
export OPENAI_API_KEY=...   # OpenAI利用時のみ
uvicorn app.main:app --reload --port 8000

# 3) エンドポイント
# 単一テキスト
curl -X POST http://localhost:8000/validate/text -H "Content-Type: application/json" -d '{
  "text": "成績評価: 小テスト20%、期末試験30%、平常点半分。週次: 第1回...第14回",
  "use_llm": true,
  "provider": "openai",
  "model": "gpt-4o-mini"
}'

# バッチ（JSON配列）
curl -X POST http://localhost:8000/validate/batch -H "Content-Type: application/json" -d @docs/sample_batch.json

# 4) CLI
python cli/syllabus_validate.py --in docs/sample_batch.json --out out.json --csv out.csv --use-llm
```

## 構成
```
app/
  main.py                # FastAPIエントリ
  validator.py           # ルール+LLM抽出の中核ロジック
  schema.py              # 入出力スキーマ
  providers/
    base.py              # LLMプロバイダIF
    openai_provider.py   # OpenAI Chat Completions(JSON)対応
    ollama_provider.py   # ローカルOllama対応
  assets/
    normalize_rules.yaml # 学内標準の用語正規化辞書
cli/
  syllabus_validate.py   # バッチ検証CLI
tests/
  test_validator.py      # ユニットテスト（合計100%/14週閾値など）
docs/
  sample_batch.json      # 合成データ（デモ/学内レビュー用）
  api_spec.md            # API仕様
  design.md              # 設計書（アーキ・データフロー・LLMプロンプト）
```

## セキュリティ/運用
- **オンプレ/学内NWで運用可能**。LLMはOllamaローカル or OpenAI選択。
- **PII/機微情報は投入前にマスキング**（拡張余地: `validator.py` に前処理フックあり）。
- APIは**入力を保存しません**（永続化無し）。必要な場合は監査ログの実装フックを用意。

## 研究発表の主張ポイント
1. ルール×LLMの**ハイブリッド抽出**で曖昧表現を安定数値化
2. **14週基準**の自動警告と**評価合計=100%**の監査
3. 正規化辞書を**学科自律更新**可能（運用コスト低）
4. API/CLI/テスト/設計を揃え、**再現性・移植性**に配慮