import base64

import streamlit as st
from anthropic import Anthropic
from pydantic import BaseModel

from utils.events import EVENT_TYPES

_MODEL = "claude-haiku-4-5-20251001"

_PROMPT_TEMPLATE = """\
以下はドッグアジリティーのイベント（公式競技会・練習会・壮行会・セミナーなど）の
告知テキストまたは告知画像です。内容を読み取り、構造化データとして抽出してください。

- event_typeは次のいずれかに分類してください: {event_types}
- 日付はすべて "YYYY-MM-DD" 形式の文字列で出力してください。年が明記されていない場合は
  文脈から妥当な年を推定してください。判別できない項目はnullにしてください。
- notesには上記のどの項目にも当てはまらない補足情報があれば記載してください。

テキスト:
{text}
"""


class EventExtraction(BaseModel):
    """AIによるイベント告知読み取り結果。"""

    name: str | None = None
    event_type: str | None = None
    organizer_name: str | None = None
    venue: str | None = None
    event_date: str | None = None
    event_end_date: str | None = None
    registration_opens_on: str | None = None
    registration_deadline: str | None = None
    registration_url: str | None = None
    registration_note: str | None = None
    notes: str | None = None


def parse_event_with_ai(
    text: str | None, image_bytes: bytes | None, mime_type: str | None
) -> dict | None:
    """テキスト・画像からClaude APIでイベント情報を構造化抽出する。

    Args:
        text: 貼り付けられた告知テキスト。
        image_bytes: アップロードされた告知画像のバイト列。
        mime_type: image_bytesのMIMEタイプ（例: "image/png"）。

    Returns:
        eventsテーブルの各項目に対応する辞書。text・image_bytesが両方とも
        無ければNoneを返す。API呼び出しやパースに失敗した場合は例外を送出する。
    """
    if not text and not image_bytes:
        return None

    content: list[dict] = []
    if image_bytes:
        content.append(
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": mime_type or "image/png",
                    "data": base64.standard_b64encode(image_bytes).decode("utf-8"),
                },
            }
        )
    content.append(
        {
            "type": "text",
            "text": _PROMPT_TEMPLATE.format(
                event_types="/".join(EVENT_TYPES), text=text or "（テキストなし。画像を参照）"
            ),
        }
    )

    client = Anthropic(api_key=st.secrets["anthropic"]["api_key"])
    response = client.messages.parse(
        model=_MODEL,
        max_tokens=1024,
        messages=[{"role": "user", "content": content}],
        output_format=EventExtraction,
    )
    return response.parsed_output.model_dump()
