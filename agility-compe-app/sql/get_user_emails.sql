-- ユーザーの氏名とメールアドレスを返すRPC関数
-- auth.usersにアクセスするためSECURITY DEFINERを使用
CREATE OR REPLACE FUNCTION get_user_emails()
RETURNS TABLE (
    user_name  text,
    email      text
)
LANGUAGE sql
SECURITY DEFINER
AS $$
    SELECT
        (raw_user_meta_data->>'name')::text AS user_name,
        email
    FROM auth.users
    ORDER BY user_name;
$$;
