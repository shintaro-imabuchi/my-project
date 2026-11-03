import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";

/**
 * サーバー側（Server Component / Server Action / Route Handler）で使う
 * Supabaseクライアント。Cookieからセッションを読み書きする。
 *
 * 呼び出すたびに最新のCookieストアを束縛するため、Server Component内で
 * （トップレベルで1回だけ生成するのではなく）都度 `await createClient()` する。
 */
export async function createClient() {
  const cookieStore = await cookies();

  return createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return cookieStore.getAll();
        },
        setAll(cookiesToSet) {
          try {
            cookiesToSet.forEach(({ name, value, options }) =>
              cookieStore.set(name, value, options),
            );
          } catch {
            // Server Componentから呼ばれた場合はCookieを書き込めない
            // （Next.jsの仕様）。middleware.tsでセッション更新している限り
            // 無視して問題ない。
          }
        },
      },
    },
  );
}
