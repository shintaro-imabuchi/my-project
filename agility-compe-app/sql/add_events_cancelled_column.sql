-- 開催中止フラグを追加する。
-- 管理画面から直接トグルする運用を想定しており、JKCデータ取り込み
-- （utils/events.py の apply_jkc_import）はこの列を一切参照・更新しないため、
-- 取り込みを再実行しても中止フラグが意図せず元に戻ることはない。
alter table events
  add column if not exists is_cancelled boolean not null default false;
