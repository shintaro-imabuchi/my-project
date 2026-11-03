import { createClient } from "@/lib/supabase/server";
import type { Competition } from "@/lib/types";

/** .env.local の NEXT_PUBLIC_COMPETITION_ID（このデプロイが扱う大会のid） */
export function getCompetitionId(): number {
  const raw = process.env.NEXT_PUBLIC_COMPETITION_ID;
  if (!raw) {
    throw new Error("NEXT_PUBLIC_COMPETITION_ID が設定されていません。");
  }
  return Number(raw);
}

export async function getCompetition(): Promise<Competition | null> {
  const supabase = await createClient();
  const { data } = await supabase
    .from("competitions")
    .select(
      "id, name, event_fees, registration_open, guideline_url, top_image_url, notice_url, home_info_message",
    )
    .eq("id", getCompetitionId())
    .single();
  return data as Competition | null;
}

/**
 * ログイン画面に表示するメッセージ。大会に紐付かない全体共通設定のため
 * competitionsではなくapp_settingsテーブル（key-value）から読み込む。
 * Streamlit版の utils/settings.py の get_login_message() と対応。
 */
export async function getLoginMessage(): Promise<string | null> {
  const supabase = await createClient();
  const { data } = await supabase
    .from("app_settings")
    .select("value")
    .eq("key", "login_message")
    .single();
  const value = data?.value;
  return typeof value === "string" && value.trim() ? value.trim() : null;
}
