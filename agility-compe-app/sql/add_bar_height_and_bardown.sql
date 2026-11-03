-- ============================================================
-- バーダウン希望機能のための追加列
-- 2026-11-03
--
-- 背景: 参加登録アプリ（Next.js版）で、種目ごとに「既定のバーの高さより
-- 低い高さ（5cm刻み）」を希望できるようにする。
--
-- 1. race_configs.bar_height: その (competition_id, event, dog_class) の
--    既定のバーの高さ（cm）。NULLなら「この種目にはバーの高さの概念がない
--    （トンネルのみの種目など）」とみなし、Next.js側はバーダウンのUIを出さない。
--    値はスタッフ画面（app_staff.py）側で設定する運用を想定（今回は列追加のみ、
--    入力UIは別途対応）。
--
-- 2. entries.bar_down_requests: 1犬のエントリーのうち、バーダウンを希望する
--    種目だけをキーに持つJSONオブジェクト。例:
--      {"AG1": 25, "JP1.5": 30}
--    希望しない種目はキー自体を持たない（＝既定の高さのまま）。
--    既存の entries.events（参加種目の配列）とは独立した列として追加するため、
--    既存のadmin/staff側のクエリ（get_entries_with_dogs等）には影響しない。
-- ============================================================

ALTER TABLE race_configs
    ADD COLUMN IF NOT EXISTS bar_height numeric(5,1);

COMMENT ON COLUMN race_configs.bar_height IS
    'この種目・クラスの既定のバーの高さ（cm）。NULLはバー高さの概念がない種目。';

ALTER TABLE entries
    ADD COLUMN IF NOT EXISTS bar_down_requests jsonb NOT NULL DEFAULT '{}'::jsonb;

COMMENT ON COLUMN entries.bar_down_requests IS
    'バーダウンを希望する種目名→希望高さ(cm)のマップ。希望しない種目はキーを持たない。';
