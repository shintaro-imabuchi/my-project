マルチ大会・マルチ主催者対応スキーマ（`sql/rebuild_multi_competition_schema.sql`）への移行に伴う、Pythonコード側の対応です。SQLはこのファイルにまとめ済み（未実行）。DBスキーマの詳細はこのSQLファイルを直接参照してください。ここでは「何をどう直すか」だけを書きます。

## 前提・方針

- ユーザー登録（氏名・メールアドレス・パスワード、`auth.users`）は今後もクラブ横断で共通。
- 参加登録・出走表・結果入力・管理者機能・スタッフ機能（`app_admin.py`・`app_staff.py`・`app_entry.py`）は、当面クラブ（大会）ごとに個別デプロイを維持する。1つのデプロイ＝1つの`competitions`行を扱う。複数大会を横断選択するUIは今回は作らない。
- 現状の管理者・スタッフ画面は、Supabase Authでログインせず「共有パスワードの一致」だけで守られており、実際のSupabase呼び出しは`anon`権限のまま行われている。新スキーマの`competitions`・`entries`・`race_configs`・`race_results`はいずれも`owner_user_id = auth.uid()`を軸にしたRLSで書き込みを制限するため、このままでは移行後に管理者・スタッフ画面からの保存が全てRLSに弾かれる。
  - 対応: 共有パスワード画面のUXはそのまま残しつつ、パスワード一致後に**裏側で**そのクラブ専用のSupabase Authアカウント（`secrets.toml`に保存したemail/password）にサインインし、`auth.uid()`を成立させる。管理者画面・スタッフ画面のどちらも同じこのアカウントでサインインしてよい（クラブ＝1アカウントという単位）。

## `.streamlit/secrets.toml` に追加が必要な項目

- `[competition] id` — このデプロイが扱う`competitions.id`
- `[admin] owner_email` / `owner_password` — そのクラブ専用のSupabase Authアカウント（新規に作成が必要。既存の`[admin] password`共有パスワードとは別物で、削除しない）

Supabase Auth側でこのアカウントを作成し、対応する`competitions`行の`owner_user_id`にそのUIDを設定する作業は、コード変更とは別に手動セットアップとして必要（このspecの対象外）。

## `supabase_client.py`

- 現在の`get_supabase()`はセッションごとにクライアントを1つ保持するだけ。これに加えて、管理者・スタッフの共有パスワード確認が通った後に呼ぶ「オーナーアカウントでサインインする」ヘルパー（例: `sign_in_as_owner()`）を追加する。二重サインインを避けるため、`st.session_state`にサインイン済みフラグを持たせる。
- 現在の`competitions.id`を取得するヘルパー（例: `get_competition_id() -> int`、`st.secrets["competition"]["id"]`を返すだけ）も追加しておくと、他ファイルからの参照が楽になる。

## `utils/settings.py`

`settings`テーブルが廃止されるため、全関数を書き換える。

- `get_registration_open` / `set_registration_open`、`get_event_fees` / `set_event_fees`、`get_guideline_url` / `set_guideline_url`、`get_top_image_url` / `set_top_image_url`、`get_notice_url` / `set_notice_url`、`get_home_info_message` / `set_home_info_message`
  → いずれも`settings`テーブルの`key`検索ではなく、`competitions`テーブルの該当`id`（`get_competition_id()`）の行の同名カラムを読み書きするように変更。
- `get_login_message` / `set_login_message`
  → 新設の`app_settings`テーブル（`key`/`value`、大会に紐付かない）に対して、これまで通り`key="login_message"`で読み書き。テーブル名だけ`settings`→`app_settings`に変更すればロジックはほぼそのまま。

## `app_admin.py`

- `check_admin_password()`が成功した直後に、`supabase_client.sign_in_as_owner()`を呼び出す。
- 各種`show_*_settings()`（event_settings, login_message_settings, link_url_settings, top_image_settings, home_info_message_settings）は、`utils.settings`の関数が競技会スコープになる以外はロジック変更不要のはず（念のため呼び出し箇所を確認）。
- `get_participants_with_dogs`RPCを呼んでいる箇所があれば、`get_entries_with_dogs(get_competition_id())`に置き換え、レスポンスの`dog_id`ベースの処理を`entry_id`ベースに直す（下記app_staff.pyと同様の変更）。

## `app_staff.py`

- `check_staff_password()`成功後にも同様に`sign_in_as_owner()`を呼ぶ。
- `fetch_participants()`: RPC呼び出しを`get_supabase().rpc("get_entries_with_dogs", {"p_competition_id": get_competition_id()})`に変更。
- `fetch_race_configs()` / `upsert_race_config()` / `delete_race_config()`:
  - `race_configs`テーブルの一意制約が`(event, dog_class)`から`(competition_id, event, dog_class)`に変更されたため、SELECT/UPSERT/DELETEすべてに`competition_id = get_competition_id()`の絞り込みを追加し、`on_conflict`も`"competition_id,event,dog_class"`に変更。UPSERT時のペイロードにも`competition_id`を含める。
- `fetch_results_for_config()`: `get_race_results` RPCの返り値スキーマは`entry_id`ベースに変わっている（`dog_id`は参考情報として残るが主キーではない）ので、呼び出し側で使うキーを`entry_id`に統一する。
- `upsert_race_result(race_config_id, dog_id, ...)`: 引数名・payload・`on_conflict`を`dog_id`→`entry_id`に変更（`race_results`テーブルが`entry_id`を参照するようになったため）。呼び出し元（`show_race_config_input`周辺、316〜375行あたり）の`p["dog_id"]`・`results_dict`のキーもすべて`entry_id`ベースに直す。

## `pages/01_dog_info.py`（最も変更が大きい箇所）

現状はここで「犬プロフィール（犬名・犬種・クラス）」と「参加種目（events）」を同時に`dogs`テーブルへ読み書きしている。新スキーマでは`dogs.events`列が廃止され、参加種目は大会ごとの`entries`テーブルに分離されるため、以下のように役割を分ける。

- 犬プロフィールの登録・変更・削除（犬名・犬種・クラス）は、引き続き`dogs`テーブルを操作。ただし`events`は扱わない。
- 「参加種目の選択」は、このページ内の別セクション、または別ページとして、現在の`competition_id`（`get_competition_id()`）と対象`dog_id`に対する`entries`行のupsert/delete（`events`列の更新）として実装し直す。既存の「犬ごとにチェックボックスで種目選択」というUIの見た目は維持してよいが、保存先を`dogs.events`ではなく`entries`（`competition_id` + `dog_id`で一意）に向ける。
- `MAX_DOGS`（1ユーザー最大4頭）の制約は犬プロフィール側の制約なので変更不要。

## `pages/02_registration_status.py`

- RPC呼び出しを`get_participants_with_dogs`から`get_entries_with_dogs(get_competition_id())`に変更するだけで、`events`キーの参照ロジック（`p.get("events")`）はそのまま動く想定。

## 動作確認の観点

- 移行SQL実行後、まず手動で対象クラブの`competitions`行を1件作成し（`owner_user_id`は新規作成したSupabase Authオーナーアカウントのuid）、`secrets.toml`の`[competition] id`をその値に合わせる。
- 参加者側（`app_entry.py`・`pages/`）: ログイン→犬情報登録→種目選択→申込状況確認、の一連の流れが通ること。
- 管理者側（`app_admin.py`）: 各種設定（受付状態・参加料・告知文・URL類）の保存が、RLSエラーなく成功すること。
- スタッフ側（`app_staff.py`）: コース設定の追加・削除、参加者一覧の取得、成績入力・保存が、RLSエラーなく成功すること。
