
# 設計書（要約）
## アーキテクチャ
- `validator.py`: ルール抽出(正規表現) + LLM抽出(プロンプトでJSON強制)
- 正規化: `assets/normalize_rules.yaml`（学内で更新）
- API: FastAPI（保存なし）
- CLI: 研究/運用スクリプト用
- テスト: pytest相当（最小例）

```
[Client/UI] -> FastAPI(/validate) -> validator (LLM+ルール) -> JSON
                                    -> normalize_rules.yaml
```

## LLMプロンプト設計
- `response_format=json_object`（OpenAI）/ `format=json`（Ollama）で**構造保証**
- 曖昧表現の比率（例「3割」「半分」）を**推定し百分率**で返す
- weeks.detected_count は本文からの**推定**（モデルの自由度を許容）

## ポリシー拡張例
- Exam > 70% なら警告
- 評価項目が2種以下なら警告
- 参考文献の5年以上比率 >30% なら警告（将来の拡張）

## 自動正規化の設計
- LLMが `normalized_label` と `confidence(0-1)` を返却
- しきい値 `AUTO_ACCEPT=0.8` 以上は自動採用。未満は辞書フォールバック
- 差分は `learn_suggestions` として返却し、管理者がYAML辞書に追記
