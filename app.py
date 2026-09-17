from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_cors import CORS
import os, json, requests

app = Flask(__name__)
CORS(app, origins='*')

GEMINI_URL = 'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent'

def call_gemini(payload):
    import time
    api_key = os.environ.get('GEMINI_API_KEY', '')
    if not api_key:
        return None, 'GEMINI_API_KEY 未設定'
    for attempt in range(4):
        try:
            r = requests.post(
                GEMINI_URL,
                headers={'x-goog-api-key': api_key, 'Content-Type': 'application/json'},
                json=payload, timeout=30
            )
            if r.status_code == 200:
                return r.json(), None
            if r.status_code in [429, 500, 502, 503, 504]:
                time.sleep(5 * (attempt + 1))
                continue
            return None, f'API 錯誤 {r.status_code}: {r.text[:200]}'
        except Exception as e:
            if attempt < 3:
                time.sleep(5 * (attempt + 1))
                continue
            return None, str(e)[:100]
    return None, '多次重試後仍失敗，請稍後再試'


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/analyze', methods=['POST'])
def analyze():
    body = request.json or {}
    marks = body.get('marks', [])
    symptoms = body.get('symptoms', {})
    description = body.get('description', '')
    user = body.get('user', '使用者')

    if not marks:
        return jsonify({'success': False, 'error': '請先在圖上標記疼痛位置'})

    view_map = {'front': '正面', 'back': '背面', 'side': '側面'}
    marks_text = '\n'.join([
        f"- {view_map.get(m.get('view',''), m.get('view',''))}：{m.get('body_part', '未知部位')}"
        + (f"（{m.get('side', '')}）" if m.get('side') else '')
        for m in marks
    ])

    timing = '、'.join(symptoms.get('timing', [])) or '未填'
    pain_type = '、'.join(symptoms.get('pain_type', [])) or '未填'
    situation = '、'.join(symptoms.get('situation', [])) or '未填'
    frequency = symptoms.get('frequency', '未填')
    level = symptoms.get('level', 5)
    duration = symptoms.get('duration', '未填')

    prompt = f"""你是一位專業的人體肌肉與筋膜治療師，專門幫助一般人（非運動員）理解日常痠痛的原因並給予按摩舒緩建議。

【使用者】{user}

【疼痛位置】
{marks_text}

【症狀描述】
- 疼痛時機：{timing}
- 疼痛性質：{pain_type}
- 可能情境：{situation}
- 發生頻率：{frequency}
- 痛覺指數：{level}/10
- 持續時間：{duration}
- 補充描述：{description or '無'}

請用繁體中文，以關心的口吻回答，避免使用太多醫學術語。格式如下：

## 🔍 可能的原因
說明這個痠痛最可能的 2-3 個原因（例如姿勢問題、肌肉緊繃、生長痛、久坐久站等），用一般人能理解的語言解釋。

## 💆 建議按摩的部位
重點說明需要放鬆的部位（**不一定是痛的地方**），解釋為什麼按這裡能緩解症狀。
每個部位用這個格式：
**部位名稱**
- 位置：在哪裡找到這個部位
- 按法：用什麼方式按（拇指按壓/掌心揉壓/手指撥動等）
- 力道：輕/中/稍重
- 時間：每次幾秒，做幾次
- 技巧：有沒有特別注意事項

## 🧘 日常改善建議
2-3 個簡單的日常調整建議，幫助預防再次發生。

## ⚠️ 需要就醫的情況
列出哪些情況出現時應該就醫，而不是繼續按摩。

注意：這是一般日常痠痛，非運動傷害，請以肌肉緊繃、筋膜沾黏、姿勢問題為主要分析方向。"""

    data, err = call_gemini({
        'contents': [{'role': 'user', 'parts': [{'text': prompt}]}],
        'generationConfig': {
            'maxOutputTokens': 2000,
            'temperature': 0.4,
            'thinkingConfig': {'thinkingBudget': 0}
        }
    })

    if err:
        return jsonify({'success': False, 'error': err})

    text = data.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', '')
    if not text:
        return jsonify({'success': False, 'error': '分析失敗，請稍後再試'})

    return jsonify({'success': True, 'result': text})


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
