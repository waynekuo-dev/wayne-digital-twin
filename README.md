# Digital Twin — 郭昭延 (Wayne) 的職涯 AI 分身

一個以 [OpenAI Agents SDK] 打造的對話式 AI，能以第一人稱回答關於 Wayne 的職涯背景、技能與專案經驗的問題。內建 **Evaluator-Optimizer** 把關機制，確保回答誠實、有事實根據，不會誇大或編造尚未具備的能力。

## 特色

- **第一人稱職涯分身**：以 Wayne 的口吻回答工作經歷、技能、專案相關問題。
- **Evaluator-Optimizer 品質把關**：每個回答在送出前都會經過一個獨立的 Evaluator Agent 檢查是否違反誠信規則，不合格會自動重新生成一次。
- **學習進度查證工具**：透過 `check_learning_progress` 工具查詢真實的學習/專案進度，避免對技能程度做出不實陳述。
- **未知問題記錄**：遇到背景資料涵蓋不到的問題，會誠實承認不確定，並透過 Pushover 推播通知 Wayne 事後補充。
- **聯絡資訊蒐集**：訪客表達合作/求職意願並留下聯絡方式時，會自動記錄並推播通知。
- **Gradio 網頁介面**：簡單易用的聊天介面。

## 架構

```
使用者訊息
   │
   ▼
Main Agent（Wayne Digital Twin）──呼叫──▶ check_learning_progress / record_unknown_question / record_user_details
   │
   ▼
Evaluator Agent（檢查是否違反誠信規則）
   │
   ├─ 通過 ──▶ 回傳給使用者
   └─ 未通過 ──▶ 帶著回饋重新生成一次 ──▶ 再次評估 ──▶ 仍不通過則回覆保底訊息 + 推播通知
```

- **Main Agent**：依據 `me/summary.txt`、`me/background.txt` 的背景資料與誠信規則回答問題。
- **Evaluator Agent**：依照同一份誠信規則，檢查回答內容與工具呼叫紀錄是否合規（輸出結構化的 `Evaluation`：`is_acceptable` / `feedback`）。
- **Pushover 推播**：無法回答的問題、連續被打回的回答、留下聯絡方式的訪客，都會即時通知 Wayne。

## 專案結構

```
digital_twin/
├── main/
│   ├── app.py              # 主程式：Agent 定義、工具、Gradio 介面
│   ├── me/
│   │   ├── summary.txt      # 背景摘要
│   │   └── background.txt   # 詳細經歷
│   └── requirements.txt
├── pyproject.toml
└── uv.lock
```

## 快速開始

### 環境需求

- Python 3.13+
- [uv](https://github.com/astral-sh/uv)（建議）或 pip

### 安裝

```bash
git clone <your-repo-url>
cd digital_twin
uv sync
```

或使用 pip：

```bash
cd main
pip install -r requirements.txt
```

### 環境變數

在專案根目錄建立 `.env` 檔案：

```env
OPENAI_API_KEY=your_openai_api_key
PUSHOVER_USER=your_pushover_user_key
PUSHOVER_TOKEN=your_pushover_app_token
```

> Pushover 相關變數若未設定，推播功能會靜默失敗，不影響核心對話功能。

### 執行

```bash
cd main
uv run app.py
```

啟動後於瀏覽器開啟 Gradio 提供的網址（預設 `http://127.0.0.1:7860`）即可開始對話。

## 技術棧

- [OpenAI Agents SDK](https://github.com/openai/openai-agents-python)
- [Gradio](https://www.gradio.app/)
- [Pydantic](https://docs.pydantic.dev/)
- [Pushover](https://pushover.net/)（即時通知）
