# 開催情報一覧（app_events_public.py）の静的サイト化 — 実装指示書

## 背景・目的

`app_events_public.py`は、JKC公式競技会などの開催情報をSupabaseの`events`テーブルから読み取って表示するだけの**完全に読み取り専用**の公開サイト（ログイン不要）。現在はStreamlit（Renderの`dog-agility-events`サービス、Starterプラン $7/月）でホストし、`agility-events.puffin.tokyo.jp`という独自ドメインで公開している。

書き込み・認証が一切ない単純な内容にもかかわらずStreamlit（SPA構成）を使っているため、以下の課題がある。

- **SEOに弱い**: ページごとの`<title>`/`<meta description>`が設定できず、検索エンジンのクロール時にJS実行が必要
- **コストが割高**: 内容はほぼ静的なのに、常時稼働のPythonプロセス（Starter $7/月）が必要

→ **静的サイト生成（SSG）に切り替える**。対象は`app_events_public.py`のみ。以下は変更しない:

- `pages/03_events.py`（`app_entry.py`・`app_staff.py`の内部関係者向け機能。Streamlitのまま）
- `app_staff.py` / `app_entry.py` 本体
- Supabaseのスキーマ・RLS・既存の管理画面（`app_admin_events.py`）

## 現状の実装（参照元）

- `app_events_public.py` — Streamlitエントリーポイント。フィルタUI＋カード表示
- `utils/events.py` — データ取得・整形ロジック。**この中の以下の関数・定数はStreamlit非依存（`st`を一切参照しない）ので、そのままimportして再利用できる**:
  - `EVENT_TYPES`, `STATUS_LABELS`, `STATUS_DEFAULT_SELECTED`
  - `get_event_status(event) -> (kind, label)` — kindは`"success"/"info"/"error"/"caption"`
  - `_to_date`（プライベートだが実質再利用可）
- Streamlit依存があるのは`get_events()`だけ（内部で`supabase_client.get_supabase()`を呼び、これが`st.secrets`を参照する）。ここだけ静的サイト側で独自実装する

### 現在のカード表示内容（テンプレート化の元ネタ）

1件のイベントにつき:
- イベント名（`is_cancelled`が真なら取り消し線）＋イベント種別バッジ（色: 公式競技会=red、練習会=blue、壮行会=orange、セミナー=green）
- 開催日（`event_date`〜`event_end_date`、終了日が開始日と同じなら単日表記）
- 会場（`venue`、あれば）
- 申込期間（`registration_opens_on`〜`registration_deadline`、どちらか片方だけの場合の表記も考慮）
- 受付状況ラベル（`get_event_status()`の戻り値。kindごとに見た目を変える: success=緑系、info=青系、error=赤系、caption=グレー）
- 「開催要項を見る」ボタン（`guideline_url`があれば）
- 「参加登録はこちら」ボタン＋「※別サイトに移動します。」の注記（`registration_url`があれば）
- どちらも無ければ「詳細・申込方法は主催者にお問い合わせください。」
- 詳細（`registration_note`・`notes`、あれば折りたたみ表示）

ページ冒頭の要素:
- タイトル「犬のアジリティー 開催情報一覧」＋「本日: YYYY/M/D」
- 説明文「公式競技会・練習会・壮行会・セミナーの開催情報をまとめています。」
- JKC転載・遅延の注記（`app_events_public.py`の`_JKC_SOURCE_NOTICE`定数をそのまま使う）
- イベント種別フィルタ（ピル、デフォルト「公式競技会」のみ）
- 受付状況フィルタ（ピル、デフォルト「申込期間中・前・未定・終了」）
- 並び順は開催日が近い順（当日以降を優先、過去分は新しい順で後ろに）

## 新しい構成

```
agility-compe-app/
  static_site/
    generate.py          # ビルドスクリプト
    requirements.txt     # supabase, jinja2 のみ（streamlit不要）
    templates/
      index.html.jinja
    static/
      style.css
      filter.js
    dist/                # 生成物の出力先（.gitignoreに追加、ビルドのたびに再生成）
```

## `static_site/generate.py` の仕様

- Streamlitに依存しない独立スクリプト。`python static_site/generate.py`で実行できる
- Supabase接続情報は**環境変数**から読む（`SUPABASE_URL` / `SUPABASE_KEY`）。`st.secrets`は使わない
  ```python
  import os
  from supabase import create_client

  def get_supabase():
      return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])
  ```
- データ取得は`utils.events.get_event_status`等をimportして流用してよいが、`get_events()`だけは上記の独自`get_supabase()`を使う版を`generate.py`内に定義する（`utils/events.py`側は変更不要）
  ```python
  def get_published_events() -> list[dict]:
      return (
          get_supabase().table("events").select("*")
          .eq("registration_open", True)
          .order("event_date")
          .execute()
          .data
      )
  ```
- 取得した全イベントに対して、`get_event_status()`で状態を計算し、テンプレートに渡すデータ（辞書のリスト）を組み立てる。フィルタ用に`event_type`・受付状況ラベルをそれぞれdata属性としてHTMLに埋め込めるようにしておく（クライアントサイドJSでの絞り込み用）
- `templates/index.html.jinja`をJinja2でレンダリングし、`dist/index.html`に書き出す
- `static/style.css`・`static/filter.js`を`dist/`にコピー（またはJinja2テンプレート内に直接埋め込んでも可、シンプルさ優先でよい）
- `robots.txt`（全許可）を`dist/robots.txt`として生成
- 実行完了時に「◯件のイベントを出力しました」を標準出力に表示

## `templates/index.html.jinja` の仕様

- `<head>`に以下を含める（現状のStreamlitでは実現できなかった部分）:
  - `<title>犬のアジリティー 開催情報一覧 | JKC公式競技会・練習会情報</title>`
  - `<meta name="description" content="JKC公式競技会をはじめ、犬のアジリティー競技会・練習会・壮行会・セミナーの開催日・会場・申込期間をまとめて確認できます。">`
  - OGPタグ（`og:title`, `og:description`, `og:type=website`, `og:url=https://agility-events.puffin.tokyo.jp/`）
  - `<link rel="canonical" href="https://agility-events.puffin.tokyo.jp/">`
- `<body>`には**全イベントを常に出力**する（フィルタで絞り込んでも、HTML上はすべてのカードが存在し続ける。JSで`display:none`を切り替えるだけ）。これによりクロール時は常に全文が見える
- 各イベントカードに`data-event-type`・`data-status-label`属性を持たせ、`filter.js`がこれを見てチェックボックス/ピル選択に応じて表示/非表示を切り替える
- フィルタUIはピルではなくチェックボックス群でよい（Streamlitの見た目に完全一致させる必要はない。シンプルな見た目に倒してよい）
- 見た目は現状のカードUIを再現する程度でよく、Streamlitの正確なピクセル再現は不要。`static/style.css`で以下を表現できれば十分:
  - カードの枠線・角丸・余白
  - イベント種別バッジの色分け（4色）
  - 受付状況ラベルの色分け（success=緑、info=青、error=赤、caption=グレー）
  - ボタン（開催要項・参加登録）
  - レスポンシブ（スマホ幅でも見られるように、`max-width`＋中央寄せ程度でよい）

## Renderへのデプロイ

1. Renderダッシュボードで**新しいStatic Site**を作成（既存の`dog-agility-events`Web Serviceとは別サービス）
   - Root Directory: `agility-compe-app`
   - Build Command: `pip install -r static_site/requirements.txt && python static_site/generate.py`
   - Publish Directory: `static_site/dist`
2. Environment Variablesに`SUPABASE_URL`・`SUPABASE_KEY`を設定（値は既存の`.streamlit/secrets.toml`の`[supabase]`セクションと同じ）
3. デプロイ後、Renderが発行する`*.onrender.com`のURLで表示確認
4. 問題なければ、独自ドメインの切り替え:
   - 新しいStatic Site側で`agility-events.puffin.tokyo.jp`をCustom Domainとして追加（認証用CNAME値が変わるはずなので確認）
   - Xserverのサーバーパネル→DNSレコード設定で、`agility-events`のCNAME値を新しい値に更新
   - 新ドメインでの表示・Google/Bingのインデックスに影響が出ないか確認
5. 旧Web Service（`dog-agility-events`）は、切り替え後しばらく残してから停止・削除する（ロールバック用）

## データ更新の反映

第一段階は**手動**でよい。`app_admin_events.py`でイベントを更新したら、RenderダッシュボードのStatic Site側で「Manual Deploy」を押して再ビルドする。

将来的に自動化する場合は、Renderの「Deploy Hook」（1本のURLにPOSTすると再ビルドが走る）を`app_admin_events.py`の保存処理（`insert_event`/`update_event`/`apply_jkc_import`/`apply_jkc_deletions`/`delete_event`呼び出し後）から叩く形にする。今回のスコープには含めない。

## 完了の目安

- `agility-events.puffin.tokyo.jp`が静的サイトから配信されている
- 現状のフィルタ・カード内容と同等の情報が表示される
- Google Search Consoleの「URL検査」で再クロールし、`<title>`/説明文が正しく認識される
- 旧Streamlit版（Render Web Service）を停止してもサイトが問題なく機能する
