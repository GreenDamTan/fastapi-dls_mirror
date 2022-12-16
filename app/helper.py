from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKeyWithSerialization
from cryptography.hazmat.primitives.serialization import load_pem_private_key, Encoding, PrivateFormat, PublicFormat, \
    NoEncryption


def load_file(filename) -> bytes:
    with open(filename, 'rb') as file:
        content = file.read()
    return content


def load_key(filename) -> RSAPrivateKeyWithSerialization:
    return load_pem_private_key(data=load_file(filename), password=None)


def private_bytes(rsa: RSAPrivateKeyWithSerialization) -> bytes:
    return rsa.private_bytes(
        encoding=Encoding.PEM,
        format=PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=NoEncryption()
    )


def public_key(rsa: RSAPrivateKeyWithSerialization) -> bytes:
    return rsa.public_key().public_bytes(
        encoding=Encoding.PEM,
        format=PublicFormat.SubjectPublicKeyInfo
    )
