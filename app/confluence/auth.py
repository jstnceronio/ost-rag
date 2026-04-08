import requests
from typing import Optional

def build_session(token: Optional[str] = None) -> requests.Session:
    session = requests.Session()

    session.headers.update({
        "Accept": "application/json",
        "User-Agent": "confluence-rag-bot/1.0",
    })

    if token:
        session.headers["Authorization"] = f"Bearer {token}"
    else:
        raise ValueError("Provide a token")

    return session