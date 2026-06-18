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

# 【検索のヒント】これが入っていれば通知（判定を軽くするために大幅に拡充）
TARGET_KEYWORDS = [
    "VRChat", "VRC", "3Dモデル", "オリジナル", "アバター", "avatar", 
    "衣装", "服", "ドレス", "スーツ", "制服", "ワンピ", "素体", "モデル", "キャラクター", "キャラ", "base", "body",
    "髪", "ヘア", "hair", "小物", "アクセ", "ギミック", "アニメーション",
    "アイテクスチャ", "目テクスチャ", "フェイステクスチャ", "顔テクスチャ", 
    "ボディテクスチャ", "肌テクスチャ", "face texture", "eye texture", "body texture"
]

# 【除外のヒント】これが入っていたら無視（テクスチャやスキンによる誤除外を防ぐため削りました）
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
        # URLそのものをアルファベット順に並び替えて保存します
        for link in sorted(seen_links):
            f.write(f"{link}\n")

# ==========================================
# 🚀 メイン処理
# ==========================================
def check_booth():
    print("=== 監視開始 ===", flush=True)
    
    # 致命的エラー検知：Discord URLが設定されていない場合は強制終了
    if not DISCORD_WEBHOOK_URL:
        print("🚨 エラー: GitHubのSecretsにDISCORD_WEBHOOK_URLが設定されていません。")
        sys.exit(1)

    seen_links = load_seen_items()
    new_seen_links = seen_links.copy()

    # 🛠 修正ポイント：コピペで改行バグが起きないよう、パーツごとに分割して結合する安全な書き方に変更しました
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
        # サイト構造の変更に備えて2パターンのクラスを検索
        items = soup.find_all("div", class_="l-cards-5col_item") or soup.find_all("li", class_="item-card")
    except Exception as e:
        print(f"🚨 BOOTHの取得エラー: {e}")
        return

    if not seen_links:
        print("ℹ️ 初回起動のためリストを初期化します。通知は行いません。")

    # 古いものから順に処理し、時系列順にDiscordへ通知させる
    items.reverse()
    
    for item in items:
        link_tag = item.find("a", href=True)
        if not link_tag:
            continue
        
        # 1. URLの厳密な整形
        href = link_tag["href"]
        if href.startswith("http"):
            link = href
        elif href.startswith("//"):
            link = f"https:{href}"
        else:
            link = f"https://booth.pm{href}"
            
        # クエリパラメータ（?utm...等）を取り除いた綺麗なURLをベースにする
        clean_link = link.split("?")[0].strip()
        
        # 既読URLならスキップ
        if clean_link in seen_links:
            continue
        
        # タイトル取得
        title_tag = item.find(class_="item-card__title") or item.find("h2")
        title = title_tag.get_text(strip=True) if title_tag else "無題"
        
        # 新しいURLを既読リストに追加（本番用）
        new_seen_links.add(clean_link)

        # 初回起動時はリストに保存するだけで通知判定はスキップ
        if not seen_links:
            continue

        # キーワード判定
        title_lower = title.lower()
        is_ignored = any(k.lower() in title_lower for k in IGNORE_KEYWORDS)
        is_target = any(k.lower() in title_lower for k in TARGET_KEYWORDS)
        
        # 条件クリアでDiscordへ送信
        if not is_ignored and is_target:
            print(f"➔ 通知対象: {title}")
            message = {"content": f"【🎁新着】{title}\n{clean_link}"}
            
            try:
                requests.post(DISCORD_WEBHOOK_URL, json=message, timeout=10)
                time.sleep(1) # Discordの連投制限対策
            except Exception as e:
                print(f"🚨 Discord通知エラー: {e}")

    # 最新の既読リストを上書き保存（本番用）
    save_seen_items(new_seen_links)
    
    print("=== 監視終了 ===", flush=True)

if __name__ == "__main__":
    check_booth()
