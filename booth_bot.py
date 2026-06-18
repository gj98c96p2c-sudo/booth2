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
        # 数字ではなく、URLそのものをアルファベット順に並び替えて保存します
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

    # スパム判定回避のためのブラウザ偽装ヘッダー
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/5
