import os
import time
import re
import json
import requests
from bs4 import BeautifulSoup

# 設定項目
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY") 
SEEN_FILE = "seen_items.txt"
BOOTH_URL = "https://booth.pm/ja/search/VRChat?max_price=0&sort=new"

# 【第1の関門】キーワードで即弾くリスト
IGNORE_KEYWORDS = [
    "ワールド", "world", "World", "WORLD", "家具", "インテリア", "ステージ", "stage",
    "部屋", "ルーム", "room", "ハウス", "house", "背景", "スカイボックス", "skybox",
    "ちふぃったー", "ちふぃった", "チフィッター", "チフィッタ", "chifitter"
]

def load_seen_items():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            return set(line.strip() for line in f if line.strip())
    return set()

def save_seen_items(seen_ids):
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        for item_id in sorted(seen_ids):
            f.write(f"{item_id}\n")

def get_item_description(item_url):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    
    # 🕵️【負荷対策】詳細ページを見に行く前に1秒待機
    time.sleep(1)
    
    try:
        res = requests.get(item_url, headers=headers, timeout=10)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, "html.parser")
            desc_tag = soup.find("div", class_="autolink") or soup.find("section", class_="item-description")
            return desc_tag.get_text(separator="\n", strip=True)[:1000]
    except:
        pass
    return ""

def call_gemini_api_json(prompt, max_retries=3):
    """Gemini APIから確実なJSON形式で返答をもらうための関数"""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
    headers = {"Content-Type": "application/json"}
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json"
        }
    }
    
    retry_delay = 10

    for attempt in range(max_retries):
        try:
            res = requests.post(url, headers=headers, json=payload, timeout=15)
            
            if res.status_code == 200:
                time.sleep(4)  # 連続リクエスト防止
                try:
                    json_str = res.json()['candidates'][0]['content']['parts'][0]['text'].strip()
                    return json.loads(json_str)
                except (KeyError, IndexError, json.JSONDecodeError) as e:
                    print(f"⚠️ APIのレスポンス解析またはJSONパースに失敗しました: {e}")
                    return None
                    
            elif res.status_code == 429:
                print(f"⏳ クォータ制限(429)を検知。{retry_delay}秒待機して再試行します... ({attempt + 1}/{max_retries})")
                time.sleep(retry_delay)
                retry_delay *= 2
                continue
            else:
                print(f"⚠️ APIエラー (Status: {res.status_code}) - {res.text[:200]}")
                return None
                
        except Exception as e:
            print(f"⚠️ API通信中に例外が発生しました: {e}")
            time.sleep(2)
            
    print("❌ 最大リトライ回数を超えたため、APIリクエストを断念します。")
    return None

def ai_filter_combined(title, description):
    """カテゴリ判定と採点を1回で行う高速・低コスト版AI審査"""
    if not GEMINI_API_KEY:
        print("⚠️ GEMINI_API_KEY が取得できていません。")
        return False

    prompt = f"""
    以下のVRChat向け商品について、審査を行い、指定のJSON形式でのみ出力してください。

    【ステップ1：カテゴリ判定】
    この商品が、VRChat向けのアバター・衣装・小物・髪型・ギミック・シェーダー・アニメーションのいずれかに該当するか判定してください。
    ※ワールド、家具、ツール、システム、単なるイラスト・写真・ロゴ、アバター本体は除外対象（is_targetをfalse）とします。

    【ステップ2：20点満点採点】
    ステップ1で対象内（true）となった場合のみ、以下の基準で合計20点満点で採点してください。対象外の場合は一律0点としてください。
    1. 品質・アクセシビリティ（10点満点）
       - 不自然な海外自動翻訳（日本語崩壊）がないか。今すぐ無料でダウンロードできるか。
    2. 導入方法・使い方の充実度（10点満点）
       - アバターへの着せ替え方、Unityでの導入手順、ギミックの使い方が記載されているか。

    【出力フォーマット】
    必ず以下の構造のJSONデータのみを出力してください。余計な解説文や挨拶は一切不要です。
    {{
        "is_target": true または false,
        "score": 算出された合計点数（半角数字のみ）
    }}

    商品タイトル: {title}
    説明文: {description[:1000]}
    """
    
    result_json = call_gemini_api_json(prompt)
    if not result_json:
        print(f"⚠️ AI審査のエラーのためスキップします: {title}")
        return False
        
    is_target = result_json.get("is_target", False)
    score = result_json.get("score", 0)
    
    print(f"🤖 AI統合審査 [{title}] -> 対象内: {is_target} / 点数: {score}点")
    
    if is_target and isinstance(score, (int, float)) and score >= 13:
        return True
        
    return False

def check_booth():
    print("=== BOOTH監視プログラム起動 ===")
    
    if not DISCORD_WEBHOOK_URL:
        print("❌ エラー: DISCORD_WEBHOOK_URL が設定されていません。")
        return

    seen_ids = load_seen_items()
    new_seen_ids = seen_ids.copy()

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)",
        "Accept-Language": "ja,en-US;q=0.9,en;q=0.8"
    }
    
    try:
        response = requests.get(BOOTH_URL, headers=headers, timeout=15)
        response.raise_for_status()
    except Exception as e:
        print(f"❌ BOOTHからのデータ取得に失敗: {e}")
        return

    soup = BeautifulSoup(response.text, "html.parser")
    items = soup.find_all("div", class_="l-cards-5col_item") or soup.find_all("div", class_="grid-item") or soup.find_all("li", class_="item-card")
    
    print(f"BOOTH上で見つかった商品ブロック数: {len(items)}件")
    items.reverse()

    send_count = 0
    for item in items:
        link_tag = item.find("a", class_="item-card__title") or item.find("a", href=True)
        if not link_tag or not link_tag.get("href"):
            continue
        
        link = link_tag["href"]
        if link.startswith("/"): 
            link = "https://booth.pm" + link
            
        # 🛠️ URLパラメータを削って純粋なIDを取得
        item_id = link.split("?")[0].rstrip("/").split("/")[-1]

        if item_id in seen_ids:
            continue
            
        title_tag = item.find(class_="item-card__title") or item.find("h2")
        title = title_tag.get_text(strip=True) if title_tag else link_tag.get_text(strip=True) or "無料の新着アイテム"

        if any(keyword.lower() in title.lower() for keyword in IGNORE_KEYWORDS):
            print(f"🚫 キーワード検知によりスキップ: {title}")
            new_seen_ids.add(item_id)
            continue

        print(f"🔍 商品詳細を読み込み中... : {title}")
        description = get_item_description(link)
        
        if not ai_filter_combined(title, description):
            print(f"🤖 AI審査不合格: {title}")
            new_seen_ids.add(item_id)
            continue

        print(f"➔ 【AI合格】新着アイテムを送信します: {title}")
        message = {
            "content": f"【🎁 新着無料VRChatアイテム】\n**商品名**: {title}\n**価格**: 無料 (0円)\n**URL**: {link}"
        }

        new_seen_ids.add(item_id)

        try:
            res = requests.post(DISCORD_WEBHOOK_URL, json=message, timeout=10)
            if res.status_code in [200, 204]:
                print(f"【通知成功】: {title}")
                send_count += 1
            else:
                print(f"⚠️ Discordへの送信に失敗 (Status: {res.status_code})")
        except Exception as e:
            print(f"❌ Discord送信エラー: {e}")
        
        # 🕵️【負荷対策】1つの商品の処理が終わったら1秒待機
        time.sleep(1)

    if send_count == 0:
        print("💡 新しい通知対象はありませんでした。")

    save_seen_items(new_seen_ids)
    print("=== 監視プログラム終了 ===")

if __name__ == "__main__":
    check_booth()
