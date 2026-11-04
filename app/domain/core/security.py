import hashlib
import hmac
import secrets
import time

from app.domain.core.config import settings

SESSION_COOKIE_NAME = "fazenda_session"
MAX_LOGIN_ATTEMPTS = 5
LOGIN_WINDOW_SECONDS = 300  # 5 minutos


def _get_signing_key() -> bytes:
    """
    Deriva a chave de assinatura HMAC combinando SECRET_KEY e ACCESS_PASSWORD.
    Assim, alterar a senha de acesso no .env invalida imediatamente todas as sessões ativas.
    """
    raw = f"{settings.SECRET_KEY}:{settings.ACCESS_PASSWORD}".encode("utf-8")
    return hashlib.sha256(raw).digest()


def verify_access_password(password: str) -> bool:
    """Compara a senha informada com ACCESS_PASSWORD em tempo constante."""
    expected = settings.ACCESS_PASSWORD
    if not password or not expected:
        return False
    return secrets.compare_digest(
        password.encode("utf-8"),
        expected.encode("utf-8"),
    )


def create_session_token(
    expires_days: int | None = None,
    now: int | None = None,
) -> str:
    """Gera um token de sessão assinado com HMAC-SHA256 e data de expiração embutida."""
    days = expires_days if expires_days is not None else settings.SESSION_EXPIRE_DAYS
    current_ts = now if now is not None else int(time.time())
    expires_at = current_ts + (days * 86400)
    nonce = secrets.token_hex(16)
    payload = f"{expires_at}.{nonce}"
    signature = hmac.new(
        _get_signing_key(),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"{payload}.{signature}"


def verify_session_token(
    token: str | None,
    now: int | None = None,
) -> bool:
    """Verifica a integridade criptográfica e a validade temporal do token de sessão."""
    if not token:
        return False

    parts = token.split(".")
    if len(parts) != 3:
        return False

    expires_str, nonce, signature = parts
    if not expires_str.isdigit() or not nonce or not signature:
        return False

    expires_at = int(expires_str)
    current_ts = now if now is not None else int(time.time())
    if current_ts >= expires_at:
        return False

    payload = f"{expires_str}.{nonce}"
    expected_sig = hmac.new(
        _get_signing_key(),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    return secrets.compare_digest(signature, expected_sig)


def sanitize_next_url(next_url: str | None) -> str:
    """Garante que a URL de redirecionamento pós-login seja um caminho interno seguro."""
    if not next_url:
        return "/"
    cleaned = next_url.strip()
    if (
        not cleaned.startswith("/")
        or cleaned.startswith("//")
        or cleaned.startswith("/\\")
        or cleaned.startswith("/login")
        or cleaned.startswith("/logout")
    ):
        return "/"
    return cleaned


class LoginRateLimiter:
    """Limitador simples em memória para proteger o endpoint de login contra força bruta."""

    def __init__(
        self,
        max_attempts: int = MAX_LOGIN_ATTEMPTS,
        window_seconds: int = LOGIN_WINDOW_SECONDS,
    ) -> None:
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._attempts: dict[str, list[float]] = {}

    def _prune(self, key: str, current_time: float) -> list[float]:
        cutoff = current_time - self.window_seconds
        valid = [ts for ts in self._attempts.get(key, []) if ts > cutoff]
        if valid:
            self._attempts[key] = valid
        else:
            self._attempts.pop(key, None)
        return valid

    def is_blocked(self, key: str, now: float | None = None) -> bool:
        current_time = now if now is not None else time.time()
        valid = self._prune(key, current_time)
        return len(valid) >= self.max_attempts

    def record_failure(self, key: str, now: float | None = None) -> None:
        current_time = now if now is not None else time.time()
        valid = self._prune(key, current_time)
        valid.append(current_time)
        self._attempts[key] = valid

    def reset(self, key: str) -> None:
        self._attempts.pop(key, None)

    def clear_all(self) -> None:
        self._attempts.clear()


login_rate_limiter = LoginRateLimiter()

