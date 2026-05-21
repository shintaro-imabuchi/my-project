-- login_message の初期行を挿入（既存行があればスキップ）
-- value は NULL で初期化し、管理者画面から設定する
INSERT INTO settings (key, value)
VALUES ('login_message', null)
ON CONFLICT (key) DO NOTHING;
