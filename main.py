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
average_temp = os.environ["AVERAGETEMP"]
high_temp =  os.environ['HIGHTEMP'] 
low_temp =  os.environ['LOWTEMP'] 
med_temp = os.environ['MEDTEMP']
tmp = os.environ['TMP']
hum = os.environ['HUM']

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
    global average_temp
    global current_user_id 
    user_id = event.source.user_id
    current_user_id = user_id
    message_text = event.message.text
    if message_text.lower() == '温度':
        if average_temp != "None":
            reply_text = f'現在の温度は {average_temp} 度です。'
        else:
            reply_text = f'温度データはありません。'
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))
    if message_text.lower() == '温度':
        reply_text = f'画像：カメラの画像データが送信されます。\n温度：温度データが送信されます。\n熱画像：カメラの熱画像データが送信されます。'
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))
    elif message_text.lower() == '画像':
        # 画像ファイルのパスを指定
        image_path = 'static/images/received_image2.jpg'
        image_message = ImageSendMessage(
            original_content_url='https://hiuser-linebot-sotuken2.onrender.com/static/images/received_image2.jpg',
            preview_image_url='https://hiuser-linebot-sotuken2.onrender.com/static/images/received_image2.jpg'
            #original_content_url='{}/{}'.format(RENDER_APP_NAME, image_path),
            #preview_image_url='{}/{}'.format(RENDER_APP_NAME, image_path) なぜか直接指定しないと動かない
        )
        line_bot_api.reply_message(event.reply_token, image_message)  
    elif message_text.lower() == '画像2':
        # 画像ファイルのパスを指定
        image_path = 'static/images/received_image.jpg'
        image_message = ImageSendMessage(
            original_content_url='https://hiuser-linebot-sotuken2.onrender.com/static/images/received_image.jpg',
            preview_image_url='https://hiuser-linebot-sotuken2.onrender.com/static/images/received_image.jpg'
            #original_content_url='{}/{}'.format(RENDER_APP_NAME, image_path),
            #preview_image_url='{}/{}'.format(RENDER_APP_NAME, image_path) なぜか直接指定しないと動かない
        )
        line_bot_api.reply_message(event.reply_token, image_message)  
        
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
        
        fallen = is_fallen(results.pose_landmarks)
        if fallen:
            message = "転倒している可能性があります"
            line_bot_api.push_message(current_user_id, TextSendMessage(text=message))
        else:
            message = "転倒している可能性があります"
            line_bot_api.push_message(current_user_id, TextSendMessage(text=message))

        # 描画された画像を新しいファイル名で保存
        output_path = os.path.join('static/images', 'received_image2.jpg')
        cv2.imwrite(output_path, image)
        return 'File successfully processed and saved as received_image2.jpg', 200
    else:
        return 'No pose detected', 400

def is_fallen(pose_landmarks):
    # 例: 頭（0番）と足（例えば左足のかかと：29番、右足のかかと：30番）のランドマークを取得
    head = pose_landmarks.landmark[0]
    left_heel = pose_landmarks.landmark[29]
    right_heel = pose_landmarks.landmark[30]

    # 頭が足よりも低い位置にあるかどうかをチェック
    if head.y > left_heel.y and head.y > right_heel.y:
        return True  # 転倒していると判断
    return False

    
@app.route('/update_env', methods=['POST'])
def update_env():
    global tmp,hum
    try:
        data = request.json
        tmp = data.get('tmp')
        hum = data.get('hum')
        
        os.environ['TMP'] = str(tmp)
        os.environ['HUM'] = str(hum)
        
        app.logger.info(f'Received temp: {tmp}')
        return {'status': 'success'}
    except Exception as e:
        print(f'Error: {str(e)}') 
        return {'status': 'error', 'message': str(e)} 

@app.route('/update_temperatures', methods=['POST'])
def update_temperatures():
    global med_temp,high_temp,low_temp,average_temp
    global current_user_id
    try:
        data = request.json
        high_temp = data.get('high_temp')
        low_temp = data.get('low_temp')
        med_temp = data.get('med_temp')
        average_temp = data.get('average_temp')
        
        # 環境変数に温度データを設定
        os.environ['HIGHTEMP'] = str(high_temp)
        os.environ['LOWTEMP'] = str(low_temp)
        os.environ['MEDTEMP'] = str(med_temp)
        os.environ['AVERAGETEMP'] = str(average_temp)
        
        if float(high_temp) > 28:
            message = "室温が28度を超えています。"
            line_bot_api.push_message(current_user_id, TextSendMessage(text=message))
        if float(high_temp) < 18:
            message = "室温が18度以下です。"
            line_bot_api.push_message(current_user_id, TextSendMessage(text=message))    
        if float(average_temp) > 100:
            message = "温度が100度を超えている場所があります。大丈夫ですか？"
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