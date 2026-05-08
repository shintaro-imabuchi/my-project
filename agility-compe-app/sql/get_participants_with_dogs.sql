-- 参加者と犬情報を結合して返すRPC関数
-- auth.usersにアクセスするためSECURITY DEFINERを使用
CREATE OR REPLACE FUNCTION get_participants_with_dogs()
RETURNS TABLE (
    dog_id     uuid,
    user_id    uuid,
    user_name  text,
    dog_name   text,
    breed      text,
    dog_class  text,
    events     text[]
)
LANGUAGE sql
SECURITY DEFINER
AS $$
    SELECT
        d.id AS dog_id,
        d.user_id,
        (u.raw_user_meta_data->>'name')::text AS user_name,
        d.dog_name,
        d.breed,
        d.dog_class,
        d.events
    FROM dogs d
    JOIN auth.users u ON d.user_id = u.id
    ORDER BY user_name, d.created_at;
$$;
