import re
from email.utils import parseaddr

def normalize_email(raw: str | None) -> str | None:
    if not raw:
        return None

    # 1) extrait l'email depuis "Name <email@domain>"
    _, email = parseaddr(raw)
    email = email.strip().lower()

    if not email or "@" not in email:
        return None

    local, domain = email.split("@", 1)

    # 2) normalisation spécifique Gmail (optionnel mais utile)
    if domain in {"gmail.com", "googlemail.com"}:
        local = local.split("+", 1)[0]      # supprime +alias
        local = local.replace(".", "")      # supprime les points
        domain = "gmail.com"

    return f"{local}@{domain}"