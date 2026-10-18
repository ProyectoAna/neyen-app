"""Genera un JWT ficticio (rol service_role) firmado con el secreto LOCAL de postgrest.conf.
Uso: make_jwt.py postgrest.conf > test.jwt   (solo para pruebas locales)"""
import base64, hashlib, hmac, json, re, sys, time


def b64(x):
    return base64.urlsafe_b64encode(x).rstrip(b"=").decode()


secret = re.search(r'jwt-secret\s*=\s*"([^"]+)"', open(sys.argv[1]).read()).group(1).encode()
head = b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
body = b64(json.dumps({"role": "service_role", "exp": int(time.time()) + 86400 * 30}).encode())
sig = b64(hmac.new(secret, f"{head}.{body}".encode(), hashlib.sha256).digest())
print(f"{head}.{body}.{sig}")
