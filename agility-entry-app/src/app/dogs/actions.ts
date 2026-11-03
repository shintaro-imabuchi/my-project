"use server";

import { revalidatePath } from "next/cache";
import { createClient } from "@/lib/supabase/server";
import { getCompetitionId } from "@/lib/competition";
import { DOG_CLASSES, type DogClass } from "@/lib/types";

function parseDogClass(value: FormDataEntryValue | null): DogClass {
  const v = String(value ?? "");
  return (DOG_CLASSES as readonly string[]).includes(v) ? (v as DogClass) : "S";
}

export async function addDog(formData: FormData) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return;

  const dogName = String(formData.get("dog_name") ?? "").trim();
  const breed = String(formData.get("breed") ?? "").trim();
  const dogClass = parseDogClass(formData.get("dog_class"));
  if (!dogName || !breed) return;

  await supabase.from("dogs").insert({
    user_id: user.id,
    dog_name: dogName,
    breed,
    dog_class: dogClass,
  });

  revalidatePath("/dogs");
}

export async function updateDog(formData: FormData) {
  const dogId = String(formData.get("dog_id") ?? "");
  const dogName = String(formData.get("dog_name") ?? "").trim();
  const breed = String(formData.get("breed") ?? "").trim();
  const dogClass = parseDogClass(formData.get("dog_class"));
  if (!dogId || !dogName || !breed) return;

  const supabase = await createClient();
  await supabase
    .from("dogs")
    .update({ dog_name: dogName, breed, dog_class: dogClass })
    .eq("id", dogId);

  revalidatePath("/dogs");
}

export async function deleteDog(formData: FormData) {
  const dogId = String(formData.get("dog_id") ?? "");
  if (!dogId) return;

  const supabase = await createClient();
  await supabase.from("dogs").delete().eq("id", dogId);

  revalidatePath("/dogs");
}

/**
 * 1頭ぶんの参加種目・バーダウン希望を保存する。
 *
 * フォームからは `event__<種目名>`（チェックボックス）と
 * `bardown__<種目名>`（希望高さ、未選択なら空文字）を受け取る。
 */
export async function saveEntry(formData: FormData) {
  const dogId = String(formData.get("dog_id") ?? "");
  if (!dogId) return;

  const events: string[] = [];
  const barDownRequests: Record<string, number> = {};

  for (const [key, value] of formData.entries()) {
    if (key.startsWith("event__") && value === "on") {
      events.push(key.slice("event__".length));
    }
  }
  for (const event of events) {
    const raw = formData.get(`bardown__${event}`);
    if (raw && String(raw) !== "") {
      barDownRequests[event] = Number(raw);
    }
  }

  const supabase = await createClient();
  const competitionId = getCompetitionId();

  if (events.length === 0) {
    await supabase
      .from("entries")
      .delete()
      .eq("competition_id", competitionId)
      .eq("dog_id", dogId);
  } else {
    await supabase.from("entries").upsert(
      {
        competition_id: competitionId,
        dog_id: dogId,
        events,
        bar_down_requests: barDownRequests,
      },
      { onConflict: "competition_id,dog_id" },
    );
  }

  revalidatePath("/dogs");
}
