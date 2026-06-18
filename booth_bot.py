import os
import sys
import time
import requests
from bs4 import BeautifulSoup

# ==========================================
# ⚙️ 設定項目
# ==========================================
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
SEEN_FILE = "seen_items.txt"
# VRChatの新着順・無料除く（全年齢向け）のURL
BOOTH_URL = "https://booth.pm/ja/search/VRChat?max_price=0&sort=new"

# 【除外キーワード】タイトルにこれが入っていたら無視（これ以外はすべて通知）
IGNORE_KEYWORDS = [
    "ワールド", "world", "家具", "インテリア", "ステージ", "部屋", "ルーム", 
    "ハウス", "背景", "スカイボックス", "bgm", "BGM", "音源", "ボイス", 
    "楽曲", "テーマ", "パーティクル"
]

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
        
        if clean_link in seen_links:
            continue
        
        title_tag = item.find(class_="item-card__title") or item.find("h2")
        title = title_tag.get_text(strip=True) if title_tag else "無題"
        
        new_seen_links.add(clean_link)

        # 💡 判定を極限までゆるく：除外ワードが入っていなければ「全部」通す！
        title_lower = title.lower()
        is_ignored = any(k.lower() in title_lower for k in IGNORE_KEYWORDS)
        
        if not is_ignored:
            print(f"➔ 通知対象: {title}")
            message = {"content": f"【🎁新着】{title}\n{clean_link}"}
            
            try:
                requests.post(DISCORD_WEBHOOK_URL, json=message, timeout=10)
                time.sleep(1) # Discord側の連投エラー防止（1秒だけでOK）
            except Exception as e:
                print(f"🚨 Discord通知エラー: {e}")

    save_seen_items(new_seen_links)
    print("=== 監視終了 ===", flush=True)

if __name__ == "__main__":
    check_booth()
