-- race_results テーブルを user_id → dog_id に変更するマイグレーション
-- テストデータを全削除してから実行する

-- 既存データをクリア
TRUNCATE race_results;

-- 古い制約・カラムを削除し、dog_id カラムを追加
ALTER TABLE race_results
    DROP CONSTRAINT race_results_race_config_id_user_id_key,
    DROP COLUMN user_id,
    ADD COLUMN dog_id uuid NOT NULL REFERENCES dogs(id) ON DELETE CASCADE,
    ADD CONSTRAINT race_results_race_config_id_dog_id_key UNIQUE (race_config_id, dog_id);
