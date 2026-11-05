import { NextResponse, type NextRequest } from "next/server";
import { createClient as createSupabaseClient } from "@supabase/supabase-js";
import { updateSession } from "@/lib/supabase/middleware";

/**
 * 大会が非公開（competitions.is_published = false）の間、トップページ
 * （準備中メッセージを表示する）と /api/health（Renderのヘルスチェック用、
 * リダイレクトすると正しく疎通確認できなくなる）以外への直接アクセスを
 * すべて "/" へリダイレクトする。ログイン・新規登録ページへの直接遷移も
 * ここでブロックされる。
 *
 * セッションCookieの更新（updateSession）とは独立した軽量なanon読み取り
 * クエリのため、Cookie連携が必要なSSRクライアントではなく
 * supabase-js（@supabase/supabase-js）のクライアントをその場で生成して使う。
 */
async function isCompetitionPublished(): Promise<boolean> {
  try {
    const supabase = createSupabaseClient(
      process.env.NEXT_PUBLIC_SUPABASE_URL!,
      process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    );
    const { data } = await supabase
      .from("competitions")
      .select("is_published")
      .eq("id", Number(process.env.NEXT_PUBLIC_COMPETITION_ID))
      .single();
    return Boolean(data?.is_published);
  } catch {
    // 取得失敗時は安全側（非公開扱い）に倒す。
    return false;
  }
}

// Next.js 16: middleware.ts は proxy.ts（エクスポート名も proxy）に改名された。
export async function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;

  if (pathname !== "/" && pathname !== "/api/health") {
    const published = await isCompetitionPublished();
    if (!published) {
      return NextResponse.redirect(new URL("/", request.url));
    }
  }

  return await updateSession(request);
}

export const config = {
  matcher: [
    /*
     * 以下を除く全パスに適用する:
     * - _next/static, _next/image（Next.js内部アセット）
     * - favicon.ico
     * - 画像拡張子のファイル
     */
    "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)",
  ],
};
