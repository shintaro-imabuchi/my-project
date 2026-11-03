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
    .select("id, name, event_fees, registration_open")
    .eq("id", getCompetitionId())
    .single();
  return data as Competition | null;
}
