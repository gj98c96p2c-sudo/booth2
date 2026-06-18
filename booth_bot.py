import os
import time
import requests
from bs4 import BeautifulSoup

# 設定項目
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
SEEN_FILE = "seen_items.txt"
BOOTH_URL = "https://booth.pm/ja/search/VRChat?max_price=0&sort=new"

# 【検索のヒント】これが入っていれば通知
TARGET_KEYWORDS = ["アバター", "衣装", "服", "ドレス", "髪", "ヘア", "小物", "ギミック", "VRC", "VRchat", "アクセ"]
# 【除外のヒント】これが入っていたら無視
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

def check_booth():
    print("=== 監視開始 ===", flush=True)
    seen_ids = load_seen_items()
    new_seen_ids = seen_ids.copy()

    # BOOTHに弾かれにくくするためのヘッダー情報
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "ja,en-US;q=0.9,en;q=0.8"
    }

    try:
        response = requests.get(BOOTH_URL, headers=headers, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        items = soup.find_all("div", class_="l-cards-5col_item") or soup.find_all("li", class_="item-card")
    except Exception as e:
        print(f"取得エラー: {e}")
        return

    # 初回起動時はすべて既読にして終了
    if not seen_ids:
        print("初回起動のためリストを初期化します。")
        for item in items:
            link_tag = item.find("a", href=True)
            if link_tag:
                href = link_tag["href"]
                temp_link = href if href.startswith("http") else f"https://booth.pm{href}"
                temp_id = temp_link.split("/")[-1].split("?")[0]
                new_seen_ids.add(temp_id)
        save_seen_items(new_seen_ids)
        return

    # 古いものから順に処理
    items.reverse()
    
    for item in items:
        link_tag = item.find("a", href=True)
        if not link_tag:
            continue
        
        # URLの結合と、パラメータを取り除いた純粋なIDの取得
        href = link_tag["href"]
        link = href if href.startswith("http") else f"https://booth.pm{href}"
        item_id = link.split("/")[-1].split("?")[0]
        
        # 既読スキップ
        if item_id in seen_ids:
            continue
        
        # タイトル取得
        title_tag = item.find(class_="item-card__title") or item.find("h2")
        title = title_tag.get_text(strip=True) if title_tag else "無題"
        
        # 既読リストに追加
        new_seen_ids.add(item_id)

        # キーワード判定（小文字に変換して効率的にチェック）
        title_lower = title.lower()
        is_ignored = any(k.lower() in title_lower for k in IGNORE_KEYWORDS)
        is_target = any(k.lower() in title_lower for k in TARGET_KEYWORDS)
        
        if not is_ignored and is_target:
            print(f"➔ 通知対象: {title}")
            message = {"content": f"【🎁新着】{title}\n{link}"}
            
            try:
                # Discordへ送信（タイムアウトも設定してフリーズを防止）
                requests.post(DISCORD_WEBHOOK_URL, json=message, timeout=10)
                time.sleep(1) # Discordの連投制限（Rate Limit）対策
            except Exception as e:
                print(f"Discord通知エラー: {e}")

    save_seen_items(new_seen_ids)
    print("=== 監視終了 ===", flush=True)

if __name__ == "__main__":
    check_booth()
