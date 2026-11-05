-- ============================================================
-- 大会の公開/非公開フラグ
-- 2026-11-05
--
-- 背景: app_admin.pyで次回大会の情報（種目設定・料金・各種お知らせ等）を
-- 登録・編集している間、参加登録アプリ（compe-entry、Next.js版）には
-- その内容を一切表示したくない。公開の準備が整った段階で、管理者が
-- 明示的に「公開する」操作をして初めてcompe-entry側に情報が出るように
-- したい。
--
-- 既存の registration_open（新規ユーザー登録の受付on/off）とは別の目的。
-- registration_openは「公開済みの大会で、今は新規登録だけ締め切る」
-- ための項目であり、is_publishedは「この大会をそもそも外部に見せるか」
-- を制御する、より上位の項目。
--
-- is_published=false の間、compe-entry（Next.js）はログイン・新規登録を
-- 含めてすべてのページをブロックし、unpublished_message の文言のみを
-- 表示する。
-- ============================================================

ALTER TABLE competitions
    ADD COLUMN IF NOT EXISTS is_published boolean NOT NULL DEFAULT false;

COMMENT ON COLUMN competitions.is_published IS
    'trueの間のみ参加登録アプリ（compe-entry）に公開される。falseの間は準備中として全ページブロックされる。';

ALTER TABLE competitions
    ADD COLUMN IF NOT EXISTS unpublished_message text;

COMMENT ON COLUMN competitions.unpublished_message IS
    'is_published=falseの間、参加登録アプリのトップに表示する文言。NULLならアプリ側のデフォルト文言を使う。';
