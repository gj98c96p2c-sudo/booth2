import os
import sys
import time
import json
import requests
from bs4 import BeautifulSoup

# ==========================================
# ⚙️ 設定項目
# ==========================================
# GitHubのSecretsから読み込み（前後の余計な空白を自動除去）
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()

SEEN_FILE = "seen_items.txt"
BOOTH_URL = "https://booth.pm/ja/search/VRChat?max_price=0&sort=new"

# 明らかなノイズ（ワールドやBGMなど）を事前に弾くリスト（AIの節約と速度向上のため）
IGNORE_KEYWORDS = [
    "ワールド", "world", "家具", "インテリア", "ステージ", "部屋", "ルーム", 
    "ハウス", "背景", "スカイボックス", "bgm", "BGM", "音源", "ボイス", 
    "楽曲", "テーマ", "パーティクル"
]

# ==========================================
# 🧠 超堅牢版：AI判定関数（Gemini API / 構造化出力）
# ==========================================
def is_vrchat_related_by_ai(title):
    # APIキーが設定されていない場合は、安全のためすべて通知する
    if not GEMINI_API_KEY:
        print("ℹ️ GEMINI_API_KEYが未設定のため、AI判定をスキップして通知します。")
        return True
        
    # 最新の安定したGeminiモデルのエンドポイント
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
    
    # 💡一発成功のための仕掛け：AIに必ず指定したJSON形式で答えさせるスキーマを設定
    payload = {
        "contents": [{
            "parts": [{
                "text": (
                    "Analyze the following BOOTH product title and determine if it is a VRChat-related asset "
                    "(such as an avatar, clothing, outfit, 3D model, hair, texture, pose, animation, gimmick, accessory, eye/face/body texture, etc.). "
                    f"Title: {title}"
                )
            }]
        }],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": {
                "type": "OBJECT",
                "properties": {
                    "related": {
                        "type": "BOOLEAN",
                        "description": "True if the title is related to VRChat assets, False otherwise."
                    }
                },
                "required": ["related"]
            }
        }
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        res_json = response.json()
        
        # AIが返したJSON文字列を解析
        text_response = res_json['candidates'][0]['content']['parts'][0]['text'].strip()
        result_data = json.loads(text_response)
        
        is_related = result_data.get("related", True)
        print(f"🤖 AI判定中... [{title}] -> 結果: {is_related}")
        return is_related

    except Exception as e:
        # 万が一AI側でエラーが起きてもボットを止めず、安全のために通知対象（True）にする
        print(f"⚠️ AI判定でエラー（またはパース失敗）が発生したため、念のため通知対象にします: {e}")
        return True

# ==========================================
# 🛠 処理用関数
# ==========================================
def load_seen_items():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            return set(line.strip() for line in f if line.strip())
    return set()

def save_seen_items(seen_links):
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        # URLをアルファベット順に綺麗に並び替えて保存
        for link in sorted(seen_links):
            f.write(f"{link}\n")

# ==========================================
# 🚀 メイン処理
# ==========================================
def check_booth():
    print("=== 監視開始 ===", flush=True)
    
    if not DISCORD_WEBHOOK_URL:
        print("🚨 エラー: GitHubのSecretsにDISCORD_WEBHOOK_URLが設定されていません。")
        sys.exit(1)

    seen_links = load_seen_items()
    new_seen_links = seen_links.copy()

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "ja,en-US;q=0.9,en;q=0.8"
    }

    try:
        response = requests.get(BOOTH_URL, headers=headers, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        items = soup.find_all("div", class_="l-cards-5col_item") or soup.find_all("li", class_="item-card")
    except Exception as e:
        print(f"🚨 BOOTHの取得エラー: {e}")
        return

    # 古い順に並び替えて時系列順にDiscordへ通知
    items.reverse()
    
    for item in items:
        link_tag = item.find("a", href=True)
        if not link_tag:
            continue
        
        href = link_tag["href"]
        if href.startswith("http"):
            link = href
        elif href.startswith("//"):
            link = f"https:{href}"
        else:
            link = f"https://booth.pm{href}"
            
        clean_link = link.split("?")[0].strip()
        
        # 既に通知済みのURLなら完全にスルー
        if clean_link in seen_links:
            continue
        
        title_tag = item.find(class_="item-card__title") or item.find("h2")
        title = title_tag.get_text(strip=True) if title_tag else "無題"
        
        # 既読リストに即座に追加
        new_seen_links.add(clean_link)

        # 1. 事前の簡易除外チェック
        title_lower = title.lower()
        if any(k.lower() in title_lower for k in IGNORE_KEYWORDS):
            print(f"⏭️ キーワード除外: [{title}]")
            continue
        
        # 2. AIによる精密検証（ここでVRChat関連アセットかを100%見極める）
        if is_vrchat_related_by_ai(title):
            print(f"➔ 通知対象確定: {title}")
            message = {"content": f"【🎁新着】{title}\n{clean_link}"}
            
            try:
                requests.post(DISCORD_WEBHOOK_URL, json=message, timeout=10)
                time.sleep(1) # 連投エラー回避のためのウェイト
            except Exception as e:
                print(f"🚨 Discord通知エラー: {e}")

    # 確実にURL形式で最新のリストを上書き保存
    save_seen_items(new_seen_links)
    print("=== 監視終了 ===", flush=True)

if __name__ == "__main__":
    check_booth()
