import { createBrowserClient } from "@supabase/ssr";

/**
 * ブラウザ（Client Component）側で使うSupabaseクライアント。
 * セッションはCookie経由で管理され、middleware.tsで自動的に更新される。
 */
export function createClient() {
  return createBrowserClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
  );
}
