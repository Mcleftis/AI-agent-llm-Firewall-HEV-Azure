import os
from dotenv import load_dotenv
import json
import base64
import time
import jwt
import pyotp
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.backends import default_backend

load_dotenv()

used_nonces = set()

TOTP_SECRET = os.getenv("TOTP_SECRET")

def verify_2fa(user_code):
    if not TOTP_SECRET:
        raise ValueError("System Error: TOTP_SECRET missing from .env")
    totp = pyotp.TOTP(TOTP_SECRET)
    return totp.verify(user_code)

class JWTManager:
    def __init__(self):
        self.secret_key = os.getenv("JWT_SECRET_KEY")
        if not self.secret_key:
            raise ValueError("System Error: JWT_SECRET_KEY missing from .env")
        self.algorithm = "HS256"

    def generate_token(self, username="admin", expiration_minutes=15):
        payload = {
            "sub": username,
            "iat": int(time.time()),
            "exp": int(time.time()) + (expiration_minutes * 60),
            "role": "vehicle_operator"
        }
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

    def verify_token(self, token):
        try:
            decoded_payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return True, decoded_payload
        except jwt.ExpiredSignatureError:
            return False, "Token has expired."
        except jwt.InvalidTokenError:
            return False, "Invalid token."

class VirtualTPM:
    def __init__(self):
        self._private_key = rsa.generate_private_key(
            public_exponent=65537, 
            key_size=2048, 
            backend=default_backend()
        )
        self._public_key = self._private_key.public_key()

    def export_private_key_for_simulation(self):
        return self._private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ).decode('utf-8')

    def export_public_key(self):
        return self._public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode('utf-8')

def generate_rsa_keys():
    tpm_module = VirtualTPM()
    return tpm_module.export_private_key_for_simulation(), tpm_module.export_public_key()

def sign_payload(pem_private_key, payload_dict):
    private_key = serialization.load_pem_private_key(
        pem_private_key.encode('utf-8'),
        password=None,
        backend=default_backend()
    )
    
    payload_bytes = json.dumps(payload_dict, sort_keys=True).encode('utf-8')
    signature = private_key.sign(
        payload_bytes,
        padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
        hashes.SHA256()
    )
    return base64.b64encode(signature).decode('utf-8')

def verify_signature(pem_public_key, payload_dict, signature_b64):
    current_time = time.time()
    msg_time = payload_dict.get('timestamp', 0)
    
    # Replay Protection
    if (current_time - msg_time > 5.0) or (msg_time - current_time > 1.0):
        return False
        
    # Nonce Validation
    nonce = payload_dict.get('nonce')
    if not nonce or nonce in used_nonces:
        return False
    used_nonces.add(nonce)

    try:
        public_key = serialization.load_pem_public_key(
            pem_public_key.encode('utf-8'), 
            backend=default_backend()
        )
        payload_bytes = json.dumps(payload_dict, sort_keys=True).encode('utf-8')
        signature = base64.b64decode(signature_b64)
        
        public_key.verify(
            signature,
            payload_bytes,
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
            hashes.SHA256()
        )
        return True
    except Exception:
        return False