from flask import Flask, request, abort ,jsonify
import requests
import os
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage, ImageMessage, ImageSendMessage, FollowEvent, UnfollowEvent
from PIL import Image
from io import BytesIO
import psycopg2
import json


LINE_CHANNEL_ACCESS_TOKEN = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
LINE_CHANNEL_SECRET = os.environ["LINE_CHANNEL_SECRET"]
DATABASE_URL = os.environ["DATABASE_URL"]
RENDER_APP_NAME = os.environ["RENDER_APP_NAME"]
averagetemp = os.environ["AVERAGETEMP"]


#averagetemp = None  # デフォルト値を設定

app = Flask(__name__)
RENDER = "https://hiuser-linebot-sotuken2.onrender.com/".format(RENDER_APP_NAME)

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

header = {
    "Content_Type": "application/json",
    "Authorization": "Bearer " + LINE_CHANNEL_ACCESS_TOKEN
}

@app.route("/")
def hello_world():
    return "hello world!"

# LINEからのWebhookを受け付けるエンドポイント
@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'OK'

# メッセージイベントのハンドリング
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    global averagetemp
    message_text = event.message.text
    if message_text.lower() == '温度':
        if averagetemp is not None:
            reply_text = f'現在の温度は {averagetemp} 度です。'
        else:
            reply_text = f'温度データはありません。{averagetemp}'
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))
    
    if message_text.lower() == '画像':
        # 画像を返信
        reply_image(event.reply_token)

# 画像を返信する関数
def reply_image(reply_token):
    image_url = image_path  # 画像のURLを指定
    line_bot_api.reply_message(
        reply_token,
        ImageSendMessage(original_content_url=image_url, preview_image_url=image_url)
    )

# averagetempを更新するエンドポイント
@app.route('/update_averagetemp', methods=['POST'])
def update_averagetemp():
    global averagetemp
    try:
        data = request.json
        averagetemp = data.get('averagetemp')
        os.environ['AVERAGETEMP'] = str(averagetemp)
        app.logger.info(f'Received averagetemp: {averagetemp}')
        return {'status': 'success'}
    except Exception as e:
        print(f'Error: {str(e)}') 
        return {'status': 'error', 'message': str(e)}

# エンドポイント：画像を受け取り、LINEに返信
@app.route('/process_image', methods=['POST'])
def process_image():
    # 画像を受け取る
    file = request.files['image']
    
    # 画像を保存
    image_path = os.path.join(UPLOAD_FOLDER, 'received_image.jpg')
    file.save(image_path)

    # LINEにメッセージと画像を送信
    send_line_message(image_path)

    return jsonify({'message': 'Image received and processed successfully'})

if __name__ == "__main__":
    app.run(debug=False)