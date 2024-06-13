import logging

logging.basicConfig()


def load_file(filename: str) -> bytes:
    log = logging.getLogger(f'{__name__}')
    log.debug(f'Loading contents of file "{filename}')
    with open(filename, 'rb') as file:
        content = file.read()
    return content


def load_key(filename: str) -> "RsaKey":
    try:
        # Crypto | Cryptodome on Debian
        from Crypto.PublicKey import RSA
        from Crypto.PublicKey.RSA import RsaKey
    except ModuleNotFoundError:
        from Cryptodome.PublicKey import RSA
        from Cryptodome.PublicKey.RSA import RsaKey

    log = logging.getLogger(__name__)
    log.debug(f'Importing RSA-Key from "{filename}"')
    return RSA.import_key(extern_key=load_file(filename), passphrase=None)


def generate_key() -> "RsaKey":
    try:
        # Crypto | Cryptodome on Debian
        from Crypto.PublicKey import RSA
        from Crypto.PublicKey.RSA import RsaKey
    except ModuleNotFoundError:
        from Cryptodome.PublicKey import RSA
        from Cryptodome.PublicKey.RSA import RsaKey
    log = logging.getLogger(__name__)
    log.debug(f'Generating RSA-Key')
    return RSA.generate(bits=2048)
