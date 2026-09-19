-- 「主催者」欄を削除。イベント名から主催クラブが分かるため冗長と判断し、
-- 公開一覧・管理画面・Facebook投稿下書きのいずれからも表示を撤去した
-- （アプリ側の対応は2026-09-19）。
-- 注: MulmoClaude側の`agility-events`コレクションの`organizer`フィールドは
-- 出陳申込書テンプレートの自動照合に使うため、削除せずそのまま残している。
-- Supabase側はその用途が無いため、列ごと削除して問題ない。
ALTER TABLE events DROP COLUMN IF EXISTS organizer_name;
