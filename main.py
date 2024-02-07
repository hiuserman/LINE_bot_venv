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
import cv2
import mediapipe as mp


LINE_CHANNEL_ACCESS_TOKEN = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
LINE_CHANNEL_SECRET = os.environ["LINE_CHANNEL_SECRET"]
DATABASE_URL = os.environ["DATABASE_URL"]
RENDER_APP_NAME = os.environ["RENDER_APP_NAME"]
averagetemp = os.environ["AVERAGETEMP"]
high_temp =  os.environ['HIGHTEMP'] 
low_temp =  os.environ['LOWTEMP'] 
med_temp = os.environ['MEDTEMP']

#averagetemp = None  # デフォルト値を設定
current_user_id = None

app = Flask(__name__)
RENDER = "https://hiuser-linebot-sotuken2.onrender.com/".format(RENDER_APP_NAME)

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

header = {
    "Content-Type": "application/json",
    "Authorization": "Bearer " + LINE_CHANNEL_ACCESS_TOKEN
}

# LINEからのWebhookを受け付けるエンドポイント
@app.route("/callback", methods=['POST'])
def callback():
    global current_user_id
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
    #global averagetemp
    global current_user_id 
    user_id = event.source.user_id
    current_user_id = user_id
    message_text = event.message.text
    if message_text.lower() == '温度':
        if med_temp is not None:
            reply_text = f'現在の温度は {med_temp} 度です。'
        else:
            reply_text = f'温度データはありません。'
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))
    elif message_text.lower() == '画像':
        # 画像ファイルのパスを指定
        image_path = 'static/images/received_image2.jpg'
        image_message = ImageSendMessage(
            original_content_url='https://hiuser-linebot-sotuken2.onrender.com/static/images/received_image2.jpg',
            preview_image_url='https://hiuser-linebot-sotuken2.onrender.com/static/images/received_image2.jpg'
            #original_content_url='{}/{}'.format(RENDER_APP_NAME, image_path),
            #preview_image_url='{}/{}'.format(RENDER_APP_NAME, image_path)
        )
        line_bot_api.reply_message(event.reply_token, image_message)   

def send_line_message(message):
    line_token = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]  # LINEのアクセストークン
    headers = {
        "Authorization": f"Bearer {line_token}",
        "Content-Type": "application/json"
    }
    data = {
        "to":  "Ub5f08338a457f448d63159f051119033",
        "messages": [
            {
                "type": "text",
                "text": message
            }
        ]
    }
    response = requests.post("https://api.line.me/v2/bot/message/push", headers=headers, json=data)
    if response.status_code != 200:
        print(f"Failed to send message: {response.text}")

def process_image(file_path):
    mp_pose = mp.solutions.pose
    pose = mp_pose.Pose()
    image = cv2.imread(file_path)
    if image is None:
        return 'Failed to load the image', 400

    results = pose.process(cv2.cvtColor(image, cv2.COLOR_BGR2RGB)) # ポーズ検出
    if results.pose_landmarks:
        # ポーズ検出された点を描画
        mp.solutions.drawing_utils.draw_landmarks(
            image, results.pose_landmarks, mp_pose.POSE_CONNECTIONS)

        # 描画された画像を新しいファイル名で保存
        output_path = os.path.join('static/images', 'received_image2.jpg')
        cv2.imwrite(output_path, image)
        return 'File successfully processed and saved as received_image2.jpg', 200
    else:
        return 'No pose detected', 400

"""
averagetempを更新するエンドポイント
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
"""

@app.route('/update_temperatures', methods=['POST'])
def update_temperatures():
    global med_temp,high_temp,low_temp
    global current_user_id
    try:
        data = request.json
        high_temp = data.get('high_temp')
        low_temp = data.get('low_temp')
        med_temp = data.get('med_temp')
        # 環境変数に温度データを設定
        os.environ['HIGHTEMP'] = str(high_temp)
        os.environ['LOWTEMP'] = str(low_temp)
        os.environ['MEDTEMP'] = str(med_temp)
        if float(high_temp) > 30:
            message = "暑いですね！温度が30度を超えました。"
            line_bot_api.push_message(current_user_id, TextSendMessage(text=message))
        app.logger.info(f'Received temp: {med_temp}')
        return {'status': 'success'}
    except Exception as e:
        print(f'Error: {str(e)}') 
        return {'status': 'error', 'message': str(e)}
   
@app.route('/receive_image', methods=['POST'])
def receive_image():
    if 'file' not in request.files:
        return 'No file part', 400
    file = request.files['file']
    if file.filename == '':
        return 'No selected file', 400
    if file:
        filename = 'received_image.jpg'  # 保存するファイル名
        file_path = os.path.join('static/images', filename)
        file.save(file_path)  # 保存先ディレクトリ
        return process_image(file_path)

if __name__ == "__main__":
    app.run(debug=False)