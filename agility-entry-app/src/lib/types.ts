// agility-compe-app（Streamlit版）と共有しているSupabaseスキーマに対応する型。
// 参照: agility-compe-app/sql/rebuild_multi_competition_schema.sql
//       agility-compe-app/sql/add_bar_height_and_bardown.sql

export const DOG_CLASSES = ["S", "M", "IM", "L"] as const;
export type DogClass = (typeof DOG_CLASSES)[number];

export const MAX_DOGS = 4;

export interface Dog {
  id: string;
  user_id: string;
  dog_name: string;
  breed: string;
  dog_class: DogClass;
  created_at: string;
}

export interface Entry {
  id: number;
  competition_id: number;
  dog_id: string;
  events: string[];
  /** 種目名 → 希望バー高さ(cm) のマップ。希望しない種目はキーを持たない */
  bar_down_requests: Record<string, number>;
  created_at: string;
  updated_at: string;
}

export interface RaceConfig {
  id: number;
  competition_id: number;
  event: string;
  dog_class: DogClass;
  course_len: number | null;
  std_time: number | null;
  limit_time: number | null;
  /** 既定のバーの高さ(cm)。nullはバー高さの概念がない種目（トンネルのみ等） */
  bar_height: number | null;
}

export interface EventFee {
  name: string;
  fee: number;
}

export interface Competition {
  id: number;
  name: string;
  event_fees: EventFee[] | null;
  registration_open: boolean;
}
