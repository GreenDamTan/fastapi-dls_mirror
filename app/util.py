import logging

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey, RSAPublicKey, generate_private_key
from cryptography.hazmat.primitives.serialization import load_pem_private_key, load_pem_public_key
from cryptography.x509 import load_pem_x509_certificate, Certificate

logging.basicConfig()


class PrivateKey:

    def __init__(self, data: bytes):
        self.__key = load_pem_private_key(data, password=None)

    @staticmethod
    def from_file(filename: str) -> "PrivateKey":
        log = logging.getLogger(__name__)
        log.debug(f'Importing RSA-Private-Key from "{filename}"')

        with open(filename, 'rb') as f:
            data = f.read()

        return PrivateKey(data=data.strip())

    def raw(self) -> RSAPrivateKey:
        return self.__key

    def pem(self) -> bytes:
        return self.__key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption()
        )

    def public_key(self) -> "PublicKey":
        data = self.__key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        return PublicKey(data=data)

    @staticmethod
    def generate(public_exponent: int = 65537, key_size: int = 2048) -> "PrivateKey":
        log = logging.getLogger(__name__)
        log.debug(f'Generating RSA-Key')
        key = generate_private_key(public_exponent=public_exponent, key_size=key_size)
        data = key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption()
        )
        return PrivateKey(data=data)


class PublicKey:

    def __init__(self, data: bytes):
        self.__key = load_pem_public_key(data)

    @staticmethod
    def from_file(filename: str) -> "PublicKey":
        log = logging.getLogger(__name__)
        log.debug(f'Importing RSA-Public-Key from "{filename}"')

        with open(filename, 'rb') as f:
            data = f.read()

        return PublicKey(data=data.strip())

    def raw(self) -> RSAPublicKey:
        return self.__key

    def pem(self) -> bytes:
        return self.__key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )


class Cert:

    def __init__(self, data: bytes):
        self.__cert = load_pem_x509_certificate(data)

    @staticmethod
    def from_file(filename: str) -> "Cert":
        log = logging.getLogger(__name__)
        log.debug(f'Importing Certificate from "{filename}"')

        with open(filename, 'rb') as f:
            data = f.read()

        return Cert(data=data.strip())

    def raw(self) -> Certificate:
        return self.__cert

    def pem(self) -> bytes:
        return self.__cert.public_bytes(encoding=serialization.Encoding.PEM)


def load_file(filename: str) -> bytes:
    log = logging.getLogger(f'{__name__}')
    log.debug(f'Loading contents of file "{filename}')
    with open(filename, 'rb') as file:
        content = file.read()
    return content


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
