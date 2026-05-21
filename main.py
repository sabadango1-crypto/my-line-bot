import os
import sys
import random
import requests
from flask import Flask, request, abort
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

# 👈 Renderの設定に合わせて、小文字でも大文字でもどちらでも読み込めるように対策しました！
channel_secret = os.environ.get('line_channel_secret') or os.environ.get('LINE_CHANNEL_SECRET')
channel_access_token = os.environ.get('line_channel_access_token') or os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')
gemini_api_key = os.environ.get('gemini_api_key') or os.environ.get('GEMINI_API_KEY')

if channel_secret is None or channel_access_token is None:
    print('Specify LINE_CHANNEL_SECRET and LINE_CHANNEL_ACCESS_TOKEN as environment variables.')
    sys.exit(1)

handler = WebhookHandler(channel_secret)
configuration = Configuration(access_token=channel_access_token)

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
    
    card = random.choice(TAROT_CARDS)
    position = random.choice(["正位置", "逆位置"])
    
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
    
    if not gemini_api_key:
        reply_text = f"🔮タロット占いの結果🔮\n\n引いたカードは【 {card} の {position} 】です！\n\n※GeminiのAPIキーが読み込めないため、カード名のみお伝えしています。"
    else:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={gemini_api_key}"
        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [{
                "parts": [{"text": prompt}]
            }]
        }
        
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            response_data = response.json()
            reply_text = response_data['candidates'][0]['content']['parts'][0]['text']
        except Exception as e:
            app.logger.error(f"Gemini API Direct Error: {e}")
            reply_text = "占い師AIとの通信でエラーが発生しました。少し時間を置いてもう一度試してみてね。"

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
