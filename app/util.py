import logging
from datetime import datetime, UTC, timedelta
from json import loads as json_loads
from os.path import join, dirname, isfile

from cryptography import x509
from cryptography.hazmat._oid import NameOID
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric.padding import PKCS1v15
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey, RSAPublicKey, generate_private_key
from cryptography.hazmat.primitives.hashes import SHA256
from cryptography.hazmat.primitives.serialization import Encoding
from cryptography.hazmat.primitives.serialization import load_pem_private_key, load_pem_public_key
from cryptography.x509 import load_pem_x509_certificate, Certificate

logging.basicConfig()


class CASetup:
    ###
    #
    # https://git.collinwebdesigns.de/nvidia/nls/-/blob/main/src/test/test_config_token.py
    #
    ###

    ROOT_PRIVATE_KEY_FILENAME = 'root_private_key.pem'
    ROOT_CERTIFICATE_FILENAME = 'root_certificate.pem'
    CA_PRIVATE_KEY_FILENAME = 'ca_private_key.pem'
    CA_CERTIFICATE_FILENAME = 'ca_certificate.pem'
    SI_PRIVATE_KEY_FILENAME = 'si_private_key.pem'
    SI_CERTIFICATE_FILENAME = 'si_certificate.pem'

    def __init__(self, service_instance_ref: str):
        self.service_instance_ref = service_instance_ref
        self.root_private_key_filename = join(dirname(__file__), 'cert', CASetup.ROOT_PRIVATE_KEY_FILENAME)
        self.root_certificate_filename = join(dirname(__file__), 'cert', CASetup.ROOT_CERTIFICATE_FILENAME)
        self.ca_private_key_filename = join(dirname(__file__), 'cert', CASetup.CA_PRIVATE_KEY_FILENAME)
        self.ca_certificate_filename = join(dirname(__file__), 'cert', CASetup.CA_CERTIFICATE_FILENAME)
        self.si_private_key_filename = join(dirname(__file__), 'cert', CASetup.SI_PRIVATE_KEY_FILENAME)
        self.si_certificate_filename = join(dirname(__file__), 'cert', CASetup.SI_CERTIFICATE_FILENAME)

        if not (isfile(self.root_private_key_filename)
                and isfile(self.root_certificate_filename)
                and isfile(self.ca_private_key_filename)
                and isfile(self.ca_certificate_filename)
                and isfile(self.si_private_key_filename)
                and isfile(self.si_certificate_filename)):
            self.init_config_token_demo()

    def init_config_token_demo(self):
        """ Create Root Key and Certificate """

        # create root keypair
        my_root_private_key = generate_private_key(public_exponent=65537, key_size=4096)
        my_root_public_key = my_root_private_key.public_key()

        # create root-certificate subject
        my_root_subject = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, u'US'),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, u'California'),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, u'Nvidia'),
            x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, u'Nvidia Licensing Service (NLS)'),
            x509.NameAttribute(NameOID.COMMON_NAME, u'NLS Root CA'),
        ])

        # create self-signed root-certificate
        my_root_certificate = (
            x509.CertificateBuilder()
            .subject_name(my_root_subject)
            .issuer_name(my_root_subject)
            .public_key(my_root_public_key)
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.now(tz=UTC) - timedelta(days=1))
            .not_valid_after(datetime.now(tz=UTC) + timedelta(days=365 * 10))
            .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
            .add_extension(x509.SubjectKeyIdentifier.from_public_key(my_root_public_key), critical=False)
            .sign(my_root_private_key, hashes.SHA256()))

        my_root_private_key_as_pem = my_root_private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )

        with open(self.root_private_key_filename, 'wb') as f:
            f.write(my_root_private_key_as_pem)

        with open(self.root_certificate_filename, 'wb') as f:
            f.write(my_root_certificate.public_bytes(encoding=Encoding.PEM))

        """ Create CA (Intermediate) Key and Certificate """

        # create ca keypair
        my_ca_private_key = generate_private_key(public_exponent=65537, key_size=4096)
        my_ca_public_key = my_ca_private_key.public_key()

        # create ca-certificate subject
        my_ca_subject = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, u'US'),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, u'California'),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, u'Nvidia'),
            x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, u'Nvidia Licensing Service (NLS)'),
            x509.NameAttribute(NameOID.COMMON_NAME, u'NLS Intermediate CA'),
        ])

        # create self-signed ca-certificate
        my_ca_certificate = (
            x509.CertificateBuilder()
            .subject_name(my_ca_subject)
            .issuer_name(my_root_subject)
            .public_key(my_ca_public_key)
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.now(tz=UTC) - timedelta(days=1))
            .not_valid_after(datetime.now(tz=UTC) + timedelta(days=365 * 10))
            .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
            .add_extension(x509.KeyUsage(
                digital_signature=False,
                key_encipherment=False,
                key_cert_sign=True,
                key_agreement=False,
                content_commitment=False,
                data_encipherment=False,
                crl_sign=True,
                encipher_only=False,
                decipher_only=False),
                critical=True
            )
            .add_extension(x509.SubjectKeyIdentifier.from_public_key(my_ca_public_key), critical=False)
            # .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(my_root_public_key), critical=False)
            .add_extension(x509.AuthorityKeyIdentifier.from_issuer_subject_key_identifier(
                my_root_certificate.extensions.get_extension_for_class(x509.SubjectKeyIdentifier).value
            ), critical=False)
            .sign(my_root_private_key, hashes.SHA256()))

        my_ca_private_key_as_pem = my_ca_private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )

        with open(self.ca_private_key_filename, 'wb') as f:
            f.write(my_ca_private_key_as_pem)

        with open(self.ca_certificate_filename, 'wb') as f:
            f.write(my_ca_certificate.public_bytes(encoding=Encoding.PEM))

        """ Create Service-Instance Key and Certificate """

        # create si keypair
        my_si_private_key = generate_private_key(public_exponent=65537, key_size=2048)
        my_si_public_key = my_si_private_key.public_key()

        my_si_private_key_as_pem = my_si_private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
        my_si_public_key_as_pem = my_si_public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )

        with open(self.si_private_key_filename, 'wb') as f:
            f.write(my_si_private_key_as_pem)

        # with open(self.si_public_key_filename, 'wb') as f:
        #    f.write(my_si_public_key_as_pem)

        # create si-certificate subject
        my_si_subject = x509.Name([
            # x509.NameAttribute(NameOID.COMMON_NAME, INSTANCE_REF),
            x509.NameAttribute(NameOID.COMMON_NAME, self.service_instance_ref),
        ])

        # create self-signed si-certificate
        my_si_certificate = (
            x509.CertificateBuilder()
            .subject_name(my_si_subject)
            .issuer_name(my_ca_subject)
            .public_key(my_si_public_key)
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.now(tz=UTC) - timedelta(days=1))
            .not_valid_after(datetime.now(tz=UTC) + timedelta(days=365 * 10))
            .add_extension(x509.KeyUsage(digital_signature=True, key_encipherment=True, key_cert_sign=False,
                                         key_agreement=True, content_commitment=False, data_encipherment=False,
                                         crl_sign=False, encipher_only=False, decipher_only=False), critical=True)
            .add_extension(x509.ExtendedKeyUsage([
                x509.oid.ExtendedKeyUsageOID.SERVER_AUTH,
                x509.oid.ExtendedKeyUsageOID.CLIENT_AUTH]
            ), critical=False)
            .add_extension(x509.SubjectKeyIdentifier.from_public_key(my_si_public_key), critical=False)
            # .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(my_ca_public_key), critical=False)
            .add_extension(x509.AuthorityKeyIdentifier.from_issuer_subject_key_identifier(
                my_ca_certificate.extensions.get_extension_for_class(x509.SubjectKeyIdentifier).value
            ), critical=False)
            .add_extension(x509.SubjectAlternativeName([
                # x509.DNSName(INSTANCE_REF)
                x509.DNSName(self.service_instance_ref)
            ]), critical=False)
            .sign(my_ca_private_key, hashes.SHA256()))

        with open(self.si_certificate_filename, 'wb') as f:
            f.write(my_si_certificate.public_bytes(encoding=Encoding.PEM))


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

    def generate_signature(self, data: bytes) -> bytes:
        return self.__key.sign(data, padding=PKCS1v15(), algorithm=SHA256())

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

    def mod(self) -> str:
        return hex(self.__key.public_numbers().n)[2:]

    def exp(self):
        return int(self.__key.public_numbers().e)

    def verify_signature(self, signature: bytes, data: bytes) -> bytes:
        return self.__key.verify(signature, data, padding=PKCS1v15(), algorithm=SHA256())


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

    def signature(self) -> bytes:
        return self.__cert.signature


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


class ProductMapping:

    def __init__(self, filename: str):
        with open(filename, 'r') as file:
            self.data = json_loads(file.read())


    def get_feature_name(self, product_name: str) -> (str, str):
        product = self.__get_product(product_name)
        product_fulfillment = self.__get_product_fulfillment(product.get('xid'))
        feature = self.__get_product_fulfillment_feature(product_fulfillment.get('xid'))

        return feature.get('feature_identifier')


    def __get_product(self, product_name: str):
        product_list = self.data.get('product')
        return next(filter(lambda _: _.get('identifier') == product_name, product_list))


    def __get_product_fulfillment(self, product_xid: str):
        product_fulfillment_list = self.data.get('product_fulfillment')
        return next(filter(lambda _: _.get('product_xid') == product_xid, product_fulfillment_list))

    def __get_product_fulfillment_feature(self, product_fulfillment_xid: str):
        feature_list = self.data.get('product_fulfillment_feature')
        features = list(filter(lambda _: _.get('product_fulfillment_xid') == product_fulfillment_xid, feature_list))
        features.sort(key=lambda _: _.get('evaluation_order_index'))
        return features[0]
