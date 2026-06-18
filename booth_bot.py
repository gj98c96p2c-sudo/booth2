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

# 【検索のヒント】これが入っていれば通知
TARGET_KEYWORDS = ["アバター", "衣装", "服", "ドレス", "髪", "ヘア", "小物", "ギミック", "VRC", "VRchat", "アクセ"]
# 【除外のヒント】これが入っていたら無視
IGNORE_KEYWORDS = ["ワールド", "world", "家具", "インテリア", "ステージ", "部屋", "ルーム", "ハウス", "背景", "スカイボックス", "bgm", "BGM", "音源", "ボイス", "楽曲", "テーマ"]

# ==========================================
# 🛠 処理用関数
# ==========================================
def load_seen_items():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            return set(line.strip() for line in f if line.strip())
    return set()

def save_seen_items(seen_ids):
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        for item_id in sorted(seen_ids):
            f.write(f"{item_id}\n")

# ==========================================
# 🚀 メイン処理
# ==========================================
def check_booth():
    print("=== 監視開始 ===", flush=True)
    
    # 致命的エラー検知：Discord URLが設定されていない場合は強制終了
    if not DISCORD_WEBHOOK_URL:
        print("🚨 エラー: GitHubのSecretsにDISCORD_WEBHOOK_URLが設定されていません。")
        sys.exit(1)

    seen_ids = load_seen_items()
    new_seen_ids = seen_ids.copy()

    # スパム判定回避のためのブラウザ偽装ヘッダー
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "ja,en-US;q=0.9,en;q=0.8"
    }

    try:
        response = requests.get(BOOTH_URL, headers=headers, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        # サイト構造の変更に備えて2パターンのクラスを検索
        items = soup.find_all("div", class_="l-cards-5col_item") or soup.find_all("li", class_="item-card")
    except Exception as e:
        print(f"🚨 BOOTHの取得エラー: {e}")
        return

    if not seen_ids:
        print("ℹ️ 初回起動のためリストを初期化します。通知は行いません。")

    # 古いものから順に処理し、時系列順にDiscordへ通知させる
    items.reverse()
    
    for item in items:
        link_tag = item.find("a", href=True)
        if not link_tag:
            continue
        
        # 1. URLの厳密な整形（特殊なプロトコル省略URL // にも対応）
        href = link_tag["href"]
        if href.startswith("http"):
            link = href
        elif href.startswith("//"):
            link = f"https:{href}"
        else:
            link = f"https://booth.pm{href}"
            
        # 2. クエリパラメータ（?utm...等）を取り除き、純粋な商品IDを取得
        item_id = link.split("?")[0].strip("/").split("/")[-1]
        
        # 既読ならスキップ
        if item_id in seen_ids:
            continue
        
        # タイトル取得
        title_tag = item.find(class_="item-card__title") or item.find("h2")
        title = title_tag.get_text(strip=True) if title_tag else "無題"
        
        # IDを既読リストに追加
        new_seen_ids.add(item_id)

        # 初回起動時はリストに保存するだけで通知判定はスキップ
        if not seen_ids:
            continue

        # キーワード判定（小文字に変換して効率的かつ漏れなくチェック）
        title_lower = title.lower()
        is_ignored = any(k.lower() in title_lower for k in IGNORE_KEYWORDS)
        is_target = any(k.lower() in title_lower for k in TARGET_KEYWORDS)
        
        # 条件クリアでDiscordへ送信
        if not is_ignored and is_target:
            print(f"➔ 通知対象: {title}")
            message = {"content": f"【🎁新着】{title}\n{link}"}
            
            try:
                requests.post(DISCORD_WEBHOOK_URL, json=message, timeout=10)
                time.sleep(1) # Discordの連投制限（Rate Limit）対策
            except Exception as e:
                print(f"🚨 Discord通知エラー: {e}")

    # 最新の既読リストを上書き保存
    save_seen_items(new_seen_ids)
    print("=== 監視終了 ===", flush=True)

if __name__ == "__main__":
    check_booth()
