# プロジェクト概要
<!-- アプリの目的・概要を記載 -->
犬のアジリティー競技会向けに、参加登録、参加者・犬一覧・競技種目別出走表・成績表作成などを行うアプリ

# 技術スタック
- Python 3.x
- Streamlit（UI・フロントエンド）
- Supabase（PostgreSQL DB・認証）
- デプロイ: Streamlit Community Cloud
- バージョン管理: GitHub

# ディレクトリ構成
my-app/
├── .streamlit/
│   ├── config.toml        # テーマ・サーバー設定
│   └── secrets.toml       # ローカル用シークレット（Git除外）
├── .venv/                  # ローカル仮想環境（Git除外）
├── .gitignore
├── CLAUDE.md
├── README.md
├── requirements.txt
├── app.py                  # エントリーポイント
├── supabase_client.py      # Supabase接続の初期化
├── pages/                  # マルチページ
│   ├── 01_page_a.py
│   └── 02_page_b.py
└── utils/
    └── helpers.py

# 環境変数・シークレット
- ローカル: .streamlit/secrets.toml で管理
- 本番: Streamlit Community Cloud の Secrets 管理画面で設定
- secrets.toml の形式:
  [supabase]
  url = "https://xxx.supabase.co"
  key = "your-anon-key"

# Supabase接続
- supabase_client.py に接続処理を集約
- 各ファイルから `from supabase_client import supabase` でimportして使う
- 認証はSupabase Authを使用

# コーディングルール
- シークレットは st.secrets["supabase"]["url"] の形式で読み込む
- 型ヒントを使う
- 関数にはdocstringを書く
- 1ファイルは200行以内を目安にする

# ローカル開発手順
1. python -m venv .venv
2. source .venv/bin/activate  # Windowsは .venv\Scripts\activate
3. pip install -r requirements.txt
4. .streamlit/secrets.toml を作成してシークレットを設定
5. streamlit run app.py

# デプロイ手順
1. GitHub にpush
2. Streamlit Community Cloud でリポジトリを連携
3. Secrets管理画面で環境変数を設定
4. 自動デプロイされることを確認

# 注意事項
- secrets.toml は絶対にGitにコミットしない（.gitignoreで除外済み）
- Supabaseのservice_role keyは使わず anon key を使う