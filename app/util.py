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
    log = logging.getLogger(__name__)
    log.debug(f'Generating RSA-Key')
    return RSA.generate(bits=2048)


class NV:
    __DRIVER_MATRIX_FILENAME = 'static/driver_matrix.json'
    __DRIVER_MATRIX: None | dict = None  # https://docs.nvidia.com/grid/ => "Driver Versions"

    def __init__(self):
        self.log = logging.getLogger(self.__class__.__name__)

        if NV.__DRIVER_MATRIX is None:
            from json import load as json_load
            try:
                file = open(NV.__DRIVER_MATRIX_FILENAME)
                NV.__DRIVER_MATRIX = json_load(file)
                file.close()
                self.log.debug(f'Successfully loaded "{NV.__DRIVER_MATRIX_FILENAME}".')
            except Exception as e:
                NV.__DRIVER_MATRIX = {}  # init empty dict to not try open file everytime, just when restarting app
                # self.log.warning(f'Failed to load "{NV.__DRIVER_MATRIX_FILENAME}": {e}')

    @staticmethod
    def find(version: str) -> dict | None:
        if NV.__DRIVER_MATRIX is None:
            return None
        for idx, (key, branch) in enumerate(NV.__DRIVER_MATRIX.items()):
            for release in branch.get('$releases'):
                linux_driver = release.get('Linux Driver')
                windows_driver = release.get('Windows Driver')
                if version == linux_driver or version == windows_driver:
                    tmp = branch.copy()
                    tmp.pop('$releases')

                    is_latest = release.get('vGPU Software') == branch.get('Latest Release in Branch')

                    return {
                        'software_branch': branch.get('vGPU Software Branch'),
                        'branch_version': release.get('vGPU Software'),
                        'driver_branch': branch.get('Driver Branch'),
                        'branch_status': branch.get('vGPU Branch Status'),
                        'release_date': release.get('Release Date'),
                        'eol': branch.get('EOL Date') if is_latest else None,
                        'is_latest': is_latest,
                    }
        return None
