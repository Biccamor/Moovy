from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
import jwt
from schemas.schemas import Settings
import datetime
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import logging

setting = Settings() # type: ignore
ph = PasswordHasher()
security = HTTPBearer()
logger = logging.getLogger(__name__)

def hash_password(password: str):
    """Zamiana hasła podanego przez uzytkownika na hash"""
    hashed = ph.hash(password=password)
    return hashed

def verify_password(hashed_password: str, password: str) -> bool:
    """Sprawdzenie czy uzytkownik podal poprawne haslo"""

    try:
        ph.verify(hashed_password, password)
        return True
    
    except VerifyMismatchError: # złe hasło po prostu
        return False
    
    except Exception as e:
        logger.error(f"ERROR {e}")
        return False

def signJWT(user_id: str) -> dict:
    """Tworzy access token (domyślnie 60 min) i długożyjący refresh token (domyślnie 14 dni)."""
    now = datetime.datetime.now(datetime.timezone.utc)

    access_payload = {
        "user_id": str(user_id),
        "type": "access",
        "exp": now + datetime.timedelta(minutes=setting.access_token_expire)
    }
    refresh_payload = {
        "user_id": str(user_id),
        "type": "refresh",
        "exp": now + datetime.timedelta(days=setting.refresh_token_expire_days)
    }

    access_token = jwt.encode(access_payload, setting.secret_key, algorithm=setting.algorithm)
    refresh_token = jwt.encode(refresh_payload, setting.secret_key, algorithm=setting.algorithm)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
    }

def decodeJWT(token: str, expected_type: str = "access") -> dict:
    """
    Dekoduje token JWT i weryfikuje jego typ.
    expected_type: "access" lub "refresh"
    Zwraca payload lub {} przy błędzie.
    """
    try:
        decoded_token = jwt.decode(token, setting.secret_key, algorithms=[setting.algorithm])
        if decoded_token.get("type") != expected_type:
            logger.error(f"Zły typ tokena — oczekiwano '{expected_type}', dostano '{decoded_token.get('type')}'")
            return {}
        return decoded_token
    except jwt.ExpiredSignatureError:
        logger.error("Token wygasł!")
        return {}
    except jwt.InvalidTokenError:
        logger.error("Nieprawidłowy token!")
        return {}


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """Wyciąga i weryfikuje access token z nagłówka Authorization."""
    token = credentials.credentials
    payload = decodeJWT(token, expected_type="access")
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload


def verify_refresh_token(token: str) -> dict:
    """
    Weryfikuje refresh token i zwraca payload.
    Rzuca HTTPException 401 jeśli token jest nieprawidłowy lub wygasł.
    """
    payload = decodeJWT(token, expected_type="refresh")
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload

def get_rate_limit_key(request) -> str:

    """
    key_func dla slowapi — identyfikuje usera po user_id z JWT tokena.
    Fallback na IP jeśli brak tokena (np. /login, /register).
    Używamy raw jwt.decode bez sprawdzania typu — key_func to tylko
    identyfikacja, nie autoryzacja.
    """
    auth: str = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth.removeprefix("Bearer ")
        try:
            payload = jwt.decode(token, setting.secret_key, algorithms=[setting.algorithm])
            user_id = payload.get("user_id")
            if user_id:
                return str(user_id)
        except Exception as e:
            logger.error(f"ERROR at get_rate_limit_key(): {e}")
    # fallback na IP dla publicznych endpointów
    return request.client.host if request.client else "unknown"
