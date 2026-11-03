/**
 * バーダウン希望の選択肢を計算するヘルパー。
 *
 * 仕様: 種目とクラスで決まる既定のバー高さ（race_configs.bar_height）より
 * 低い高さを、5cm刻み・実際の高さ（cm）そのもので希望できる。
 * 下限は実際の高さで20cmまで。
 */
export const BAR_DOWN_STEP_CM = 5;
export const MIN_BAR_HEIGHT_CM = 20;

/**
 * 既定のバー高さから選べるバーダウン高さ（実際の高さ、cm）の一覧を返す（高い順）。
 * 例: defaultHeight=35 → [30, 25, 20]
 * 例: defaultHeight=20 → []（既に下限のため選択肢なし）
 */
export function barDownOptions(defaultHeight: number): number[] {
  const options: number[] = [];
  for (
    let height = defaultHeight - BAR_DOWN_STEP_CM;
    height >= MIN_BAR_HEIGHT_CM;
    height -= BAR_DOWN_STEP_CM
  ) {
    options.push(height);
  }
  return options;
}
