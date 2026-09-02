-- 「Facebook投稿下書き」機能の投稿済み管理は不要と判断し廃止したため、
-- 対応する posted_milestones テーブルも削除する（任意・実行しなくても
-- アプリの動作に支障はない。単に使われなくなった空テーブルが残るだけ）。
DROP TABLE IF EXISTS posted_milestones;
