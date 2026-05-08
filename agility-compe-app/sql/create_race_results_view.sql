-- 種目・クラス別成績一覧を返す RPC 関数
-- 減点・スピード・旋回スピードを計算済みで返す
-- 注意: time はPostgreSQLの予約語のため run_time に変更
-- race_results は dog_id で dogs テーブルと紐付け
CREATE OR REPLACE FUNCTION get_race_results(p_race_config_id bigint)
RETURNS TABLE (
    result_id       bigint,
    dog_id          uuid,
    user_id         uuid,
    user_name       text,
    dog_name        text,
    breed           text,
    dog_class       text,
    run_time        numeric,
    fail            smallint,
    refuse          smallint,
    deduct          numeric,
    speed           numeric,
    course_len      numeric,
    std_time        numeric,
    limit_time      numeric,
    turning_speed   numeric,
    updated_at      timestamptz
)
LANGUAGE sql
SECURITY DEFINER
AS $$
    SELECT
        rr.id                                                           AS result_id,
        rr.dog_id,
        d.user_id,
        (u.raw_user_meta_data->>'name')::text                          AS user_name,
        d.dog_name,
        d.breed,
        d.dog_class,
        rr.time                                                         AS run_time,
        rr.fail,
        rr.refuse,
        CASE
            WHEN rr.time = 0 THEN NULL
            ELSE round(
                ((rr.fail + rr.refuse) * 5
                 + GREATEST(0, rr.time - COALESCE(rc.std_time, 0)))::numeric,
                2
            )
        END                                                             AS deduct,
        CASE
            WHEN rr.time > 0 THEN round((rc.course_len / rr.time)::numeric, 2)
            ELSE NULL
        END                                                             AS speed,
        rc.course_len,
        rc.std_time,
        rc.limit_time,
        round((rc.course_len / NULLIF(rc.std_time, 0))::numeric, 2)   AS turning_speed,
        rr.updated_at
    FROM race_results rr
    JOIN race_configs rc ON rr.race_config_id = rc.id
    JOIN dogs         d  ON d.id              = rr.dog_id
    JOIN auth.users   u  ON u.id              = d.user_id
    WHERE rr.race_config_id = p_race_config_id;
$$;
