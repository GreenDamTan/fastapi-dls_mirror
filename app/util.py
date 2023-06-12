def load_file(filename) -> bytes:
    with open(filename, 'rb') as file:
        content = file.read()
    return content


def load_key(filename) -> "RsaKey":
    try:
        # Crypto | Cryptodome on Debian
        from Crypto.PublicKey import RSA
        from Crypto.PublicKey.RSA import RsaKey
    except ModuleNotFoundError:
        from Cryptodome.PublicKey import RSA
        from Cryptodome.PublicKey.RSA import RsaKey

    return RSA.import_key(extern_key=load_file(filename), passphrase=None)


def parse_key(content: bytes) -> "RsaKey":
    try:
        # Crypto | Cryptodome on Debian
        from Crypto.PublicKey import RSA
        from Crypto.PublicKey.RSA import RsaKey
    except ModuleNotFoundError:
        from Cryptodome.PublicKey import RSA
        from Cryptodome.PublicKey.RSA import RsaKey

    return RSA.import_key(extern_key=content, passphrase=None)


def generate_key() -> "RsaKey":
    try:
        # Crypto | Cryptodome on Debian
        from Crypto.PublicKey import RSA
        from Crypto.PublicKey.RSA import RsaKey
    except ModuleNotFoundError:
        from Cryptodome.PublicKey import RSA
        from Cryptodome.PublicKey.RSA import RsaKey

    return RSA.generate(bits=2048)
