# 讓圖片可以不要一直重複覆寫，改用 UUID 生成唯一的檔名
from flask import Flask, request, abort, send_from_directory
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage, ImageSendMessage
from openai import AzureOpenAI
import os
import requests
import json
import uuid

app = Flask(__name__)

# LINE Bot 的 Channel Access Token 和 Channel Secret
LINE_CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_SECRET = os.getenv('LINE_CHANNEL_SECRET')

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# Azure OpenAI 設定
client = AzureOpenAI(
    api_version=os.getenv('api_version'),
    api_key=os.getenv('api_key'),
    azure_endpoint=os.getenv('azure_endpoint')
)

# ngrok url
ngrok_url = os.getenv('ngrok_url')
print(f"ngrok url: {ngrok_url}")

@app.route("/callback", methods=['POST'])
def callback():
    # 獲取 X-Line-Signature 標頭的值
    signature = request.headers['X-Line-Signature']

    # 獲取請求的主體作為文本
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    # 處理 webhook 主體
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_prompt = event.message.text  # 使用者輸入的文字

    try:
        # 生成圖片
        result = client.images.generate(
            model="dall-e-3",
            prompt=user_prompt,
            n=1
        )
        
        json_response = json.loads(result.model_dump_json())
        image_url = json_response["data"][0]["url"]  # 從回應中取得圖片 URL
        
        # 儲存圖片到本地資料夾
        image_dir = os.path.join(os.curdir, 'images')
        if not os.path.isdir(image_dir):
            os.mkdir(image_dir)
        
        # 使用 UUID 生成唯一的檔名
        unique_filename = f"{uuid.uuid4()}.png"
        image_path = os.path.join(image_dir, unique_filename)

        generated_image = requests.get(image_url).content  # 下載圖片
        with open(image_path, "wb") as image_file:
            image_file.write(generated_image)

        # 印出原始圖片網址以方便除錯
        print(f"原始圖片網址: {image_url}")

        # 準備圖片訊息回覆
        reply_messages = [
            ImageSendMessage(
                original_content_url=f"{ngrok_url}/images/{unique_filename}",
                preview_image_url=f"{ngrok_url}/images/{unique_filename}"
            ),
            # TextSendMessage(text=f"已生成圖片，儲存在: {image_path}")
        ]
    except Exception as e:
        # 錯誤處理：回覆錯誤訊息
        reply_messages = [TextSendMessage(text=f"圖片生成失敗: {str(e)}")]

    # 單一呼叫 reply_message 回覆使用者
    line_bot_api.reply_message(event.reply_token, reply_messages)

@app.route('/images/<filename>')
def send_image(filename):
    return send_from_directory('images', filename)

if __name__ == "__main__":
    app.run()
