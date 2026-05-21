import os
import sys
import random
from flask import Flask, request, abort
from google import genai  # 👈 Geminiの新しいライブラリ
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent

app = Flask(__name__)

# 環境変数から各鍵を取得
channel_secret = os.environ.get('LINE_CHANNEL_SECRET')
channel_access_token = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')
gemini_api_key = os.environ.get('GEMINI_API_KEY')  # 👈 Geminiの鍵

if channel_secret is None or channel_access_token is None:
    print('Specify LINE_CHANNEL_SECRET and LINE_CHANNEL_ACCESS_TOKEN as environment variables.')
    sys.exit(1)

handler = WebhookHandler(channel_secret)
configuration = Configuration(access_token=channel_access_token)

# Geminiクライアントの初期化（キーがあれば有効化）
gemini_client = None
if gemini_api_key:
    gemini_client = genai.Client(api_key=gemini_api_key)

# 22枚の大アルカナカードのリスト
TAROT_CARDS = [
    "0. 愚者", "I. 魔術師", "II. 女教皇", "III. 女帝", "IV. 皇帝", "V. 法王",
    "VI. 恋人", "VII. 戦車", "VIII. 正義", "IX. 隠者", "X. 運命の輪", "XI. 力",
    "XII. 吊るされた男", "XIII. 死神", "XIV. 節制", "XV. 悪魔", "XVI. 塔",
    "XVII. 星", "XVIII. 月", "XIX. 太陽", "XX. 審判", "XXI. 世界"
]

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        app.logger.info("Invalid signature. Please check your channel access token/channel secret.")
        abort(400)

    return 'OK'

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    user_message = event.message.text
    
    # Geminiの準備ができていない場合は、通常のメッセージを返す
    if not gemini_client:
        reply_text = "占い師（Gemini）の準備ができていません。環境変数を確認してください。"
    else:
        # 1. 内部でタロットカードと位置をランダムに決定
        card = random.choice(TAROT_CARDS)
        position = random.choice(["正位置", "逆位置"])
        
        # 2. Geminiに送るための指示書（プロンプト）を作成
        prompt = f"""
        あなたは親切で当たると評判のプロのタロット占い師です。
        ユーザーから以下のお悩みや相談が届きました。
        
        【ユーザーの相談】: {user_message}
        
        あなたが引いたタロットカードは【 {card} の {position} 】です。
        
        以下の条件を必ず守って、ユーザーへの鑑定結果・アドバイスを作成してください。
        ・文頭は「🔮タロット占いの結果をお伝えします🔮」から始めてください。
        ・引いたカードの名前と向きを明記してください。
        ・そのカードが持つ一般的な意味を、今回の相談内容に絡めて優しく解説してください。
        ・最後には、ユーザーが一歩踏み出せるような具体的なアドバイスや応援の言葉で締めくくってください。
        ・全体の文章量は250文字〜400文字程度にまとめ、LINEで見やすいよう適度に改行を入れてください。
        """
        
        try:
            # 3. Geminiに鑑定文を作ってもらう
            response = gemini_client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
            )
            reply_text = response.text
        except Exception as e:
            app.logger.error(f"Gemini API Error: {e}")
            reply_text = "占い中にエラーが発生しました。少し時間を置いてもう一度話しかけてね。"

    # LINEに返事を送る
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message_with_http_info(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply_text)]
            )
        )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
