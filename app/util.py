try:
    # Crypto | Cryptodome on Debian
    from Crypto.PublicKey import RSA
    from Crypto.PublicKey.RSA import RsaKey
except ModuleNotFoundError:
    from Cryptodome.PublicKey import RSA
    from Cryptodome.PublicKey.RSA import RsaKey


def load_file(filename) -> bytes:
    with open(filename, 'rb') as file:
        content = file.read()
    return content


def load_key(filename) -> RsaKey:
    return RSA.import_key(extern_key=load_file(filename), passphrase=None)
