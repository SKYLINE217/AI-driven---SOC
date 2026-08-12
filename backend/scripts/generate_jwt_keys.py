"""
Generate an RS256 keypair for JWT signing.

Usage:
    python -m backend.scripts.generate_jwt_keys

Outputs:
    keys/jwt_private.pem  — keep secret, set as JWT_PRIVATE_KEY_PATH
    keys/jwt_public.pem   — safe to share, set as JWT_PUBLIC_KEY_PATH
"""

from __future__ import annotations

from pathlib import Path

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


def generate_keypair(output_dir: str = "keys") -> None:
    out = Path(output_dir)
    out.mkdir(exist_ok=True)

    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend(),
    )

    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )

    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    (out / "jwt_private.pem").write_bytes(private_pem)
    (out / "jwt_public.pem").write_bytes(public_pem)

    print(f"[OK] Private key: {out / 'jwt_private.pem'}")
    print(f"[OK] Public key:  {out / 'jwt_public.pem'}")
    print()
    print("Set these environment variables:")
    print(f"  JWT_PRIVATE_KEY_PATH={out / 'jwt_private.pem'}")
    print(f"  JWT_PUBLIC_KEY_PATH={out / 'jwt_public.pem'}")
    print()
    print("WARNING: Never commit jwt_private.pem to git.")


if __name__ == "__main__":
    generate_keypair()
