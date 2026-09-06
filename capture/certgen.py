# -*- coding: utf-8 -*-
"""证书管理：自签 CA + 按需签发目标证书（ cryptography 零外部依赖）。

CA 持久化在 %APPDATA%/SecondClass/ca/，安装到当前用户受信任根后
本机小程序流量即可被本地代理解密。
"""
import datetime
import os
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from core.config import data_dir


def ca_dir() -> Path:
    d = Path(data_dir()) / "ca"
    d.mkdir(parents=True, exist_ok=True)
    return d


def ca_key_path() -> Path:
    return ca_dir() / "ca.key.pem"


def ca_cert_path() -> Path:
    """PEM 格式的 CA 证书（内部使用）。"""
    return ca_dir() / "ca.cert.pem"


def ca_cer_path() -> Path:
    """DER 格式的 CA 证书（certutil 安装用）。"""
    return ca_dir() / "ca.cer"


def _utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def ensure_ca() -> tuple:
    """确保 CA 密钥与证书存在；返回 (key_pem, cert_pem)。"""
    key_path = ca_key_path()
    cert_path = ca_cert_path()
    if key_path.exists() and cert_path.exists():
        key_pem = key_path.read_text(encoding="utf-8")
        cert_pem = cert_path.read_text(encoding="utf-8")
        return key_pem, cert_pem
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, "SecondClass Local Proxy CA"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "SecondClass"),
    ])
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(_utcnow() - datetime.timedelta(days=1))
        .not_valid_after(_utcnow() + datetime.timedelta(days=3650))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(x509.KeyUsage(
            digital_signature=True, key_encipherment=True,
            key_cert_sign=True, crl_sign=True, content_commitment=False,
            data_encipherment=False, key_agreement=False, encipher_only=False,
            decipher_only=False), critical=True)
        .sign(key, hashes.SHA256())
    )
    key_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption()).decode("utf-8")
    cert_pem = cert.public_bytes(serialization.Encoding.PEM).decode("utf-8")
    key_path.write_text(key_pem, encoding="utf-8")
    cert_path.write_text(cert_pem, encoding="utf-8")
    # DER 副本供 certutil 安装
    ca_cer_path().write_bytes(cert.public_bytes(serialization.Encoding.DER))
    return key_pem, cert_pem


def load_ca():
    """返回 (ca_key_obj, ca_cert_obj)。"""
    from cryptography.hazmat.primitives.serialization import load_pem_private_key, load_pem_public_key
    key_pem, cert_pem = ensure_ca()
    key = load_pem_private_key(key_pem.encode("utf-8"), password=None)
    cert = x509.load_pem_x509_certificate(cert_pem.encode("utf-8"))
    return key, cert


def issue_cert(host: str, days: int = 30) -> tuple:
    """为 host 签发服务器证书；返回 (key_pem_bytes, cert_pem_bytes)。"""
    ca_key, ca_cert = load_ca()
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, host),
    ])
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(ca_cert.subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(_utcnow() - datetime.timedelta(days=1))
        .not_valid_after(_utcnow() + datetime.timedelta(days=days))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(x509.SubjectAlternativeName([x509.DNSName(host)]), critical=False)
        .add_extension(x509.KeyUsage(
            digital_signature=True, key_encipherment=True,
            key_cert_sign=False, crl_sign=False, content_commitment=False,
            data_encipherment=False, key_agreement=False, encipher_only=False,
            decipher_only=False), critical=True)
        .sign(ca_key, hashes.SHA256())
    )
    key_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption())
    cert_pem = cert.public_bytes(serialization.Encoding.PEM)
    return key_pem, cert_pem


def ca_fingerprint() -> str:
    """返回 CA 证书指纹（大写十六进制，无冒号），用于检测是否已信任。"""
    _key, cert = load_ca()
    return cert.fingerprint(hashes.SHA256()).hex().upper()
