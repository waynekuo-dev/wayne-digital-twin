import os
import requests
import gradio as gr
from pydantic import BaseModel
from dotenv import load_dotenv
from agents import Agent, Runner, function_tool, trace

load_dotenv(override=True)

# ---------- 設定變數 ----------
NAME = "郭昭延 (Chao-Yen Kuo / Wayne)"
MODEL = "gpt-5.4-mini"

# ---------- 0. Pushover 推播設定 ----------
PUSHOVER_USER = os.getenv("PUSHOVER_USER")
PUSHOVER_TOKEN = os.getenv("PUSHOVER_TOKEN")
PUSHOVER_URL = "https://api.pushover.net/1/messages.json"


def push(message: str):
    payload = {"user": PUSHOVER_USER,
               "token": PUSHOVER_TOKEN, "message": message}
    requests.post(PUSHOVER_URL, data=payload, timeout=30)


# ---------- 1. 讀取背景資料 ----------
with open("me/summary.txt", "r", encoding="utf-8") as f:
    SUMMARY = f.read()

with open("me/background.txt", "r", encoding="utf-8") as f:
    BACKGROUND = f.read()

# ---------- 2. 學習進度表（防止幻覺，回答前必須查證） ----------
LEARNING_PROGRESS = {
    "深度學習": "進行中，目前上到 CNN/ResNet，尚未學到 Transformer、GPT、GAN、Diffusion 等後續章節",
    "Kubernetes": "已學到 K8s 核心概念（Pod、Deployment、PVC、Ingress）與 Minikube 本地端部署，"
                  "尚未學到 AWS EKS / GCP GKE 雲端部署",
    "Flask": "課程已上完，目前仍在複習鞏固階段，尚未到非常熟練的程度",
    "FastAPI": "課程已上完，目前仍在複習鞏固階段，尚未到非常熟練的程度",
    "Django": "課程已上完，目前仍在複習鞏固階段，尚未到非常熟練的程度",
    "離散數學": "尚未開始學習",
    "資料結構與演算法": "尚未開始學習",
    "線性代數": "尚未開始學習",
    "職稱": "目前在 Gogoro 的正式職稱是「工程師」，工作內容屬於 Data Scientist 的範疇，"
    "並非正式職稱就是 Data Scientist",
    "AWS": "AWS 基礎課程（VPC/EC2/S3/RDS/IAM）已學完，具備基礎雲端架構知識；"
           "「圖解 AWS+GCP：雲端雙平台入門」課程的 AWS 部分也已上完；"
           "但「圖解 AWS：打造分散式雲端架構」這門進階課程目前仍在進行中、尚未上完，"
           "不能說已經具備分散式雲端架構的實戰經驗",
    "GCP": "GCP 相關課程完全尚未開始學習",
    "RAG": "自主開發的 RAG 失效分析知識庫原型（LangChain、Chroma、Llama 3），只完成技術驗證 demo，"
           "並未正式上線或持續維護；後續因主管決定交由 data team 統一開發，此專案並未繼續深化",
}

TOPIC_ALIASES = {
    "k8s": "kubernetes",
    "title": "職稱",
    "job title": "職稱",
    "position": "職稱",
    "職位": "職稱",
    "cloud": "aws gcp",
    "雲端": "aws gcp",
    "knowledge base": "rag",
    "知識庫": "rag",
}


@function_tool
def check_learning_progress(topic: str) -> str:
    """查詢 Wayne 在特定技術主題上的真實學習進度。
    在回答任何關於技能、課程進度、專案完成度的問題之前，一律要先呼叫這個工具查證，
    絕對不能憑印象或臆測回答。如果問題一次涉及多個主題，把完整問題傳進來即可，
    這個工具會把命中的每個主題都回傳，不需要為了每個主題個別呼叫一次。

    Args:
        topic: 想查詢的技術主題關鍵字或原始問題，例如「深度學習」「RAG」「Kubernetes」「職稱」
    """
    normalized = topic.strip().lower()
    for alias, canonical in TOPIC_ALIASES.items():
        if alias in normalized:
            normalized = f"{normalized} {canonical}"

    matches = {
        key: value
        for key, value in LEARNING_PROGRESS.items()
        if key.lower() in normalized or normalized in key.lower()
    }
    if not matches:
        result = (f"「{topic}」不在需要特別查證的進度清單中，代表這個主題沒有誇大或講錯的風險，"
                  f"可以直接依照背景資料（summary/background）正常回答，不需要說不確定，"
                  f"也不需要呼叫 record_unknown_question。只有當背景資料裡也完全找不到這個主題時，"
                  f"才需要如實告知不確定並呼叫 record_unknown_question 記錄。")
    else:
        result = "\n".join(f"【{key}】{value}" for key, value in matches.items())

    print(f"[工具呼叫] check_learning_progress(topic={topic!r}) -> {result}")
    return result


# ---------- 3. 記錄工具（透過 Pushover 推播） ----------
@function_tool
def record_unknown_question(question: str) -> str:
    """當你無法回答某個問題時，用這個工具記錄下來，方便 Wayne 事後補充。

    Args:
        question: 無法回答的問題內容
    """
    push(f"[Digital Twin] 無法回答的問題：{question}")
    print(f"[工具呼叫] record_unknown_question(question={question!r})")
    return "已記錄這個問題，Wayne 會後續補充回答。"


@function_tool
def record_user_details(email: str = "", name: str = "未提供姓名",
                        notes: str = "", contact_method: str = "") -> str:
    """當對方表示想留下聯絡方式、想進一步跟 Wayne 聯繫時，用這個工具記錄。
    email 不是必填：如果對方沒有留 email，但留了其他聯絡方式（LinkedIn、電話、微信等），
    一樣要呼叫這個工具，把該聯絡方式放進 contact_method，不要因為沒有 email 就不記錄。

    Args:
        email: 對方的電子郵件（如果有提供）
        name: 對方的姓名（如果有提供）
        notes: 其他補充資訊，例如對方的公司、職缺、談話重點
        contact_method: 當對方沒有提供 email 時，用這個欄位記錄其他聯絡方式，
            例如 LinkedIn 網址、電話號碼、微信 ID
    """
    contact = email or contact_method or "未提供聯絡方式"
    push(f"[Digital Twin] 有人留下聯絡方式：{name} / {contact} / {notes}")
    print(
        f"[工具呼叫] record_user_details(name={name!r}, contact={contact!r}, notes={notes!r})")
    return "已記錄聯絡資訊，謝謝！Wayne 會盡快跟你聯繫。"


# ---------- 4. Guardrail 規則（Wayne 最在意的誠實原則，Evaluator 會依此把關） ----------
GUARDRAIL_RULES = """
【重要規則，絕對不能違反】
1. RAG專案上線狀態、職稱、深度學習學習進度、離散數學/資料結構與演算法/線性代數的學習狀態、
   Flask/FastAPI/Django熟練度、Kubernetes部署範圍，以及任何其他技能、課程進度、專案完成度
   的問題，都必須先呼叫 check_learning_progress 工具查證、並以查詢結果為準再回答，不可以
   憑印象或臆測回答，就算答案感覺已經在背景資料裡看過，也要走一次工具查證，不能只憑背景
   資料裡的文字直接回答。
2. 如果對方問的是跟 Wayne 職涯背景相關、但背景資料沒有涵蓋到的問題（例如到職日期、薪資期望、
   私人生活細節），誠實說不確定，並呼叫 record_unknown_question 工具記錄下來，絕對不要編造
   答案。這條不適用於規則4定義的離題問題——離題問題只需要照規則4處理，不要呼叫
   record_unknown_question，因為那不是「Wayne 需要事後補充回答」的問題，記錄了只會製造無意義
   的通知。
3. 如果對方問「你是真人還是AI」，必須誠實、清楚地說明自己是 Wayne 的 AI Digital Twin，不能裝作
   自己就是本人，也不能迴避這個問題。
4. 只回答跟 Wayne 的職涯、背景、技能、經驗相關的問題；如果對方問到完全無關的話題（例如天氣、
   八卦），禮貌地把對話導回專業話題，不要順著離題內容聊下去，也不要呼叫 record_unknown_question。
5. 對方表示想聯絡 Wayne、想留下聯絡方式，屬於正常且歡迎的求職/合作互動，不算離題（不適用第4條），
   應該鼓勵對方留下 email 並呼叫 record_user_details 工具記錄，不能拒絕或迴避。如果對方沒有
   email、只留了其他聯絡方式（例如 LinkedIn、電話、微信），一樣要呼叫 record_user_details
   把該聯絡方式記錄進 contact_method 欄位，絕對不能因為沒有 email 就不記錄。
6. 你是在回答「關於 Wayne」的問題，不是在幫對方做事。不要主動提議幫對方整理、草擬、
   產生文件（例如面試自我介紹稿、履歷、求職信等），這種服務型提議會讓對方以為在跟通用
   AI 助理互動，而不是在了解 Wayne 本人。
"""

INSTRUCTIONS = f"""你正在扮演 {NAME}，以第一人稱回答關於他的職涯、背景、技能與經驗的問題。
你的語氣專業、誠懇、謙虛但有自信，符合一位資深工程師轉職資料科學家/AI工程師的形象。
回答盡量簡潔扼要，像真人對話一樣自然，不要長篇大論。

【背景摘要】
{SUMMARY}

【詳細經歷】
{BACKGROUND}

{GUARDRAIL_RULES}
"""

main_agent = Agent(
    name="Wayne Digital Twin",
    instructions=INSTRUCTIONS,
    tools=[check_learning_progress,
           record_unknown_question, record_user_details],
    model=MODEL,
)


# ---------- 5. Evaluator Agent（Evaluator-Optimizer 模式：二次檢查，沒過就重跑） ----------
class Evaluation(BaseModel):
    is_acceptable: bool
    feedback: str


evaluator_agent = Agent(
    name="Guardrail Evaluator",
    instructions=f"""你是品質把關者，負責檢查一段代表 {NAME} 回答的內容，是否違反以下規則：

{GUARDRAIL_RULES}

以下是 {NAME} 真實的背景資料，是判斷「回答內容有沒有事實根據」的唯一依據：

【背景摘要】
{SUMMARY}

【詳細經歷】
{BACKGROUND}

你會收到「這一輪的完整對話紀錄」（包含使用者訊息、助理的工具呼叫細節、工具回傳結果）以及
「待檢查的回答」。除了檢查回答文字本身有沒有誇大或錯誤資訊，也要檢查流程是否合規：
- 如果使用者問的是技能、課程進度、專案完成度相關問題，對話紀錄裡必須看得到
  check_learning_progress 這個工具被實際呼叫過（規則 1）。如果答案內容跟技能/進度有關，
  但紀錄裡完全沒有這個工具的呼叫紀錄，一律視為違反規則 1，回傳 is_acceptable=False。
- 如果回答內容包含具體的承諾、數字或事實（例如到職日期、薪資期望、私人生活細節等），
  但這些內容在上面的背景資料裡完全找不到根據、也不是工具查詢結果提供的，這就是憑空編造
  （規則 2：不確定就該老實說不確定並記錄，不能編答案）。這種情況下，對話紀錄裡必須看得到
  record_unknown_question 被呼叫過；如果回答提供了背景資料沒有的具體承諾、卻沒有呼叫
  record_unknown_question，一律視為違反規則 2，回傳 is_acceptable=False。
- 如果對方留下了聯絡方式（email 或其他聯絡方式），對話紀錄裡必須看得到 record_user_details
  被呼叫過（規則 5）。沒有呼叫也視為違反，回傳 is_acceptable=False。

如果回答內容跟流程都完全符合規則，回傳 is_acceptable=True。
如果有任何一條被違反（例如誇大專案完成度、講錯職稱、提到還沒學的技術、講錯課程進度、
編造背景資料沒有的具體事實、該查證卻沒呼叫工具、該記錄聯絡方式卻沒呼叫工具），回傳
is_acceptable=False，並在 feedback 具體指出哪一條規則被違反、應該怎麼修正。""",
    output_type=Evaluation,
    model=MODEL,
)


async def get_reply(message: str, raw_history: list) -> tuple[str, list]:
    """主流程：主 Agent 回答 -> Evaluator 檢查 -> 沒過就帶著回饋重新生成"""
    input_messages = raw_history + [{"role": "user", "content": message}]

    with trace("Wayne Digital Twin Conversation"):
        result = await Runner.run(main_agent, input_messages)
        reply = result.final_output

        # 用 to_input_list() 而不是 input_messages，因為前者才包含「這一輪」實際
        # 發生的工具呼叫細節；只給 Evaluator input_messages 的話，它永遠看不到
        # 這一輪有沒有真的呼叫 check_learning_progress / record_user_details，
        # 等於沒辦法查核規則 1/5 有沒有被遵守。
        this_turn_trace = result.to_input_list()

        eval_result = await Runner.run(
            evaluator_agent,
            f"這一輪的完整對話紀錄（含工具呼叫細節）：{this_turn_trace}\n\n待檢查的回答：{reply}",
        )
        evaluation = eval_result.final_output

        if not evaluation.is_acceptable:
            print(f"[Evaluator 打回] 原因：{evaluation.feedback}")
            retry_messages = input_messages + [
                {"role": "assistant", "content": reply},
                {
                    "role": "system",
                    "content": f"這個回答被品質把關者退回，原因：{evaluation.feedback}。"
                    f"請根據這個回饋重新生成一個符合規則的回答。",
                },
            ]
            result = await Runner.run(main_agent, retry_messages)
            reply = result.final_output

            second_trace = result.to_input_list()
            eval_result = await Runner.run(
                evaluator_agent,
                f"這一輪的完整對話紀錄（含工具呼叫細節）：{second_trace}\n\n待檢查的回答：{reply}",
            )
            evaluation = eval_result.final_output
            if not evaluation.is_acceptable:
                print(f"[Evaluator 二次打回] 原因：{evaluation.feedback}")
                push(f"[Digital Twin] Evaluator 連續兩次打回同一個回答\n"
                     f"問題：{message}\n原因：{evaluation.feedback}")
                reply = ("不好意思，這題我這邊沒辦法給出滿意的答案，"
                         "要不要換個方式問，或是問我其他關於經歷背景的問題？")
                # 存進歷史的內容必須跟使用者實際看到的一致：如果直接用
                # result.to_input_list()，存進去的會是那個被打回、使用者根本
                # 沒看過的原始回答，導致之後的對話紀錄跟畫面顯示的內容對不上，
                # 之後這個或 Evaluator 可能誤以為自己真的講過那句話。
                # 這一輪本來就被判定不合格，工具呼叫細節不留進歷史也合理。
                new_raw_history = input_messages + \
                    [{"role": "assistant", "content": reply}]
                return reply, new_raw_history

    new_raw_history = result.to_input_list()
    return reply, new_raw_history


# ---------- 6. Gradio 介面 ----------
# 不用 gr.ChatInterface，改用 gr.Blocks 手動組，避開 ChatInterface 內部一定會夾帶的
# BrowserState（它每次重啟都用新的隨機密鑰加密 localStorage 資料，導致舊資料解密失敗、
# JSON.parse 出錯，整個頁面掛掉，且無法透過 ChatInterface 的公開參數關閉這個元件）。
# raw_history 是 to_input_list() 的完整紀錄（含工具呼叫細節），跟畫面上顯示用的
# chatbot 訊息分開存放，兩者互不干擾。

with gr.Blocks(title=f"和 {NAME} 聊聊他的職涯背景") as demo:
    gr.Markdown(f"# {NAME} 的職涯分身")
    gr.Markdown(
        "這是 Wayne Digital Twin，"
        "可以問他關於工作經歷、技能、專案、學習歷程的任何問題。"
    )
    chatbot = gr.Chatbot()  # 畫面上顯示用的訊息紀錄
    msg = gr.Textbox(placeholder="輸入訊息...", show_label=False)
    raw_history_state = gr.State([])  # 存放 get_reply() 需要的完整 raw_history
    # 暫存使用者輸入的原始文字，供 add_bot_reply 使用。不能從 chat_history[-1]["content"]
    # 反推：chat_history 會先經過 chatbot 元件 round-trip，Gradio 6.x 把純字串正規化成
    # [{"text": ..., "type": "text"}]，這個結構送進 OpenAI Responses API 會因為
    # type 要 "input_text" 而非 "text" 被 400 打回來。
    pending_message_state = gr.State("")

    def add_user_message(message, chat_history):
        chat_history = chat_history + [{"role": "user", "content": message}]
        return chat_history, "", message

    async def add_bot_reply(pending_message, chat_history, raw_history):
        reply, new_raw_history = await get_reply(pending_message, raw_history)
        chat_history = chat_history + [{"role": "assistant", "content": reply}]
        return chat_history, new_raw_history

    msg.submit(
        add_user_message,
        [msg, chatbot],
        [chatbot, msg, pending_message_state],
    ).then(
        add_bot_reply,
        [pending_message_state, chatbot, raw_history_state],
        [chatbot, raw_history_state],
    )

if __name__ == "__main__":
    demo.launch()
