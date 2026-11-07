"""Double authentification TOTP (RFC 6238, compatible Google Authenticator,
Microsoft Authenticator, FreeOTP...) et codes de secours, sans dépendance."""
import base64
import hashlib
import hmac
import json
import secrets
import struct
import time
from urllib.parse import quote

from werkzeug.security import generate_password_hash, check_password_hash

STEP = 30
DIGITS = 6


def new_secret():
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")


def _code(secret, step):
    key = base64.b32decode(secret + "=" * (-len(secret) % 8), casefold=True)
    digest = hmac.new(key, struct.pack(">Q", step), hashlib.sha1).digest()
    off = digest[-1] & 0x0F
    n = (struct.unpack(">I", digest[off:off + 4])[0] & 0x7FFFFFFF) % (10 ** DIGITS)
    return f"{n:0{DIGITS}d}"


def verify(secret, code, last_step=None, window=1):
    """Retourne le pas de temps accepté (à mémoriser contre le rejeu), ou None."""
    code = (code or "").replace(" ", "")
    if not secret or not code.isdigit() or len(code) != DIGITS:
        return None
    now = int(time.time()) // STEP
    for step in range(now - window, now + window + 1):
        if last_step is not None and step <= last_step:
            continue
        if hmac.compare_digest(_code(secret, step), code):
            return step
    return None


def uri(secret, account, issuer):
    label = quote(f"{issuer}:{account}")
    return f"otpauth://totp/{label}?secret={secret}&issuer={quote(issuer)}&digits={DIGITS}&period={STEP}"


def new_recovery_codes(n=8):
    """Retourne (codes en clair à afficher une fois, valeur à stocker)."""
    codes = [f"{secrets.token_hex(2)}-{secrets.token_hex(2)}" for _ in range(n)]
    return codes, json.dumps([generate_password_hash(c) for c in codes])


def use_recovery_code(stored, code):
    """Retourne la nouvelle valeur stockée si le code est valide (consommé), sinon None."""
    code = (code or "").strip().lower()
    try:
        hashes = json.loads(stored or "[]")
    except ValueError:
        return None
    for i, h in enumerate(hashes):
        if check_password_hash(h, code):
            return json.dumps(hashes[:i] + hashes[i + 1:])
    return None


def remaining(stored):
    try:
        return len(json.loads(stored or "[]"))
    except ValueError:
        return 0


def password_problem(password, email=""):
    """Politique de mot de passe : None si conforme, sinon le message d'erreur."""
    if len(password or "") < 12:
        return "Le mot de passe doit contenir au moins 12 caractères."
    classes = sum(any(f(ch) for ch in password) for f in (str.islower, str.isupper, str.isdigit,
                                                          lambda ch: not ch.isalnum()))
    if classes < 3:
        return "Le mot de passe doit mêler au moins 3 types de caractères (minuscules, majuscules, chiffres, symboles)."
    if email and email.split("@")[0].lower() in password.lower():
        return "Le mot de passe ne doit pas contenir votre identifiant."
    return None


def temporary_password():
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789"
    while True:
        pw = "".join(secrets.choice(alphabet) for _ in range(12)) + secrets.choice("!#%+=?@") + secrets.choice("23456789")
        if password_problem(pw) is None:
            return pw
