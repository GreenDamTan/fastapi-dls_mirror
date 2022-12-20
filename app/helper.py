from Crypto.PublicKey import RSA
from Crypto.PublicKey.RSA import RsaKey


def load_file(filename) -> bytes:
    with open(filename, 'rb') as file:
        content = file.read()
    return content


def load_key(filename) -> RsaKey:
    return RSA.import_key(extern_key=load_file(filename), passphrase=None)


def private_bytes(rsa: RsaKey) -> bytes:
    return rsa.export_key(format='PEM', passphrase=None, protection=None)


def public_key(rsa: RsaKey) -> bytes:
    return rsa.public_key().export_key(format='PEM')
