import hashlib
import os
import base64

try:
    from pwdlib import PasswordHash
    password_hash = PasswordHash.recommended()
    # Test if it actually works
    password_hash.hash("test")
    USE_PWD_LIB = True
except Exception:
    USE_PWD_LIB = False


def hash_password(password: str) -> str:
    if USE_PWD_LIB:
        try:
            return password_hash.hash(password)
        except Exception:
            pass

    # Fallback to standard library pbkdf2
    salt = os.urandom(16)
    db_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
    return f"pbkdf2_sha256$100000${base64.b64encode(salt).decode('utf-8')}${base64.b64encode(db_hash).decode('utf-8')}"


def verify_password(password: str, hashed_password: str) -> bool:
    if USE_PWD_LIB and not hashed_password.startswith("pbkdf2_sha256$"):
        try:
            return password_hash.verify(password, hashed_password)
        except Exception:
            pass

    if hashed_password.startswith("pbkdf2_sha256$"):
        try:
            parts = hashed_password.split('$')
            iterations = int(parts[1])
            salt = base64.b64decode(parts[2])
            old_hash = base64.b64decode(parts[3])
            new_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, iterations)
            return old_hash == new_hash
        except Exception:
            return False

    return False