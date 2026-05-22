from __future__ import annotations

from pathlib import Path

import requests


def send_message(token: str, chat_id: str, text: str) -> None:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    response = requests.post(url, data={"chat_id": chat_id, "text": text}, timeout=30)
    response.raise_for_status()
    payload = response.json()
    if not payload.get("ok"):
        raise RuntimeError(f"Telegram sendMessage failed: {payload}")


def send_document(token: str, chat_id: str, path: Path, caption: str) -> None:
    url = f"https://api.telegram.org/bot{token}/sendDocument"
    with path.open("rb") as handle:
        response = requests.post(
            url,
            data={"chat_id": chat_id, "caption": caption},
            files={"document": (path.name, handle, "application/pdf")},
            timeout=120,
        )
    response.raise_for_status()
    payload = response.json()
    if not payload.get("ok"):
        raise RuntimeError(f"Telegram sendDocument failed: {payload}")

