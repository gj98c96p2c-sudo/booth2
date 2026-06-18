import os
import time
import json
import requests
from bs4 import BeautifulSoup

# 設定項目
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY") 
SEEN_FILE = "seen_items.txt"
BOOTH_URL = "https://booth.pm/ja/search/VRChat?max_price=0&sort=new"

# 即弾くリスト（APIを無駄遣いしないための防波堤）
IGNORE_KEYWORDS = ["ワールド", "world", "家具", "インテリア", "ステージ", "部屋", "ルーム", "ハウス", "背景", "スカイボックス", "bgm", "BGM", "音源", "ボイス", "楽曲", "テーマ"]

def load_seen_items():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            return set(line.strip() for line in f if line.strip())
    return set()

def save_seen_items(seen_ids):
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        for item_id in sorted(seen_ids):
            f.write(f"{item_id}\n")

def call_gemini_api_json(prompt):
    """タイトル判定専用の軽量API呼び出し"""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
    payload = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"responseMimeType": "application/json"}}
    
    try:
        res = requests.post(url, headers={"Content-Type": "application/json"}, json=payload, timeout=10)
        if res.status_code == 200:
            time.sleep(4) # 制限回避の待機
            return json.loads(res.json()['candidates'][0]['content']['parts'][0]['text'])
        return None
    except:
        return None

def is_vrchat_item(title):
    """タイトルだけをAIに投げて判定"""
    prompt = f'商品タイトルが「VRChat向けのアバター・衣装・小物・ギミック」か判定してください。ワールド、家具、ツール、音楽、ロゴは除外。JSONで {{"is_target": true/false}} のみ出力して。タイトル: {title}'
    result = call_gemini_api_json(prompt)
    return result.get("is_target", False) if result else False

def check_booth():
    print("=== 監視開始 ===", flush=True)
    seen_ids = load_seen_items()
    new_seen_ids = seen_ids.copy()

    try:
        response = requests.get(BOOTH_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        soup = BeautifulSoup(response.text, "html.parser")
        items = soup.find_all("div", class_="l-cards-5col_item")
    except:
        return

    # 初回起動時の既読保存（初回は通知なし）
    if len(seen_ids) == 0:
        for item in items:
            link = item.find("a", href=True)
            if link: new_seen_ids.add(link["href"].split("/")[-1])
        save_seen_items(new_seen_ids)
        return

    items.reverse()
    for item in items:
        link_tag = item.find("a", href=True)
        if not link_tag: continue
        
        link = "https://booth.pm" + link_tag["href"]
        item_id = link.split("/")[-1]
        if item_id in seen_ids: continue
        
        title = item.find(class_="item-card__title").get_text(strip=True)
        new_seen_ids.add(item_id)

        # キーワードフィルター
        if any(k in title for k in IGNORE_KEYWORDS): continue
        
        # タイトルAI判定
        if is_vrchat_item(title):
            print(f"➔ 通知対象: {title}")
            requests.post(DISCORD_WEBHOOK_URL, json={"content": f"【🎁新着】{title}\n{link}"})
            time.sleep(1)

    save_seen_items(new_seen_ids)
    print("=== 終了 ===", flush=True)

if __name__ == "__main__":
    check_booth()
