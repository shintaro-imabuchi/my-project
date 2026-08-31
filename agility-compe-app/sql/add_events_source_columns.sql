-- ============================================================
-- events: JKC等の外部情報源との連携用に列を追加
-- 2026-08-30
--
-- source_id: MulmoClaudeの`agility-events`コレクション側のレコードID
--   （例: "shinshu-kitayatsugatake-ag-2026-09-12"）を保持する。
--   一意制約を付け、取り込み時に upsert(on_conflict="source_id") で
--   「既存なら更新・無ければ新規作成」を安全に行えるようにする。
--   手動登録したイベント（JKC由来でないもの）はNULLのままでよい
--   （UNIQUE制約下でNULL同士は重複とみなされない）。
-- guideline_url: 開催要項PDF等のURL。公式競技会は郵送申込が基本で
--   registration_url（参加登録サイトのURL）という概念が当てはまらない
--   ことが多いため、別列として新設する。
-- ============================================================

ALTER TABLE events ADD COLUMN IF NOT EXISTS source_id text UNIQUE;
ALTER TABLE events ADD COLUMN IF NOT EXISTS guideline_url text;
