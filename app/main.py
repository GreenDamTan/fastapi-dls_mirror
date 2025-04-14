import logging
from base64 import b64encode as b64enc
from calendar import timegm
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, UTC
from hashlib import sha256
from json import loads as json_loads
from os import getenv as env
from os.path import join, dirname, isfile
from random import randbytes
from uuid import uuid4

from dateutil.relativedelta import relativedelta
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.requests import Request
from jose import jws, jwk, jwt, JWTError
from jose.constants import ALGORITHMS
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import StreamingResponse, JSONResponse as JSONr, HTMLResponse as HTMLr, Response, RedirectResponse

from orm import Origin, Lease, init as db_init, migrate
from util import PrivateKey, PublicKey, load_file, Cert, ProductMapping

# Load variables
load_dotenv('../version.env')

# Get current timezone
TZ = datetime.now().astimezone().tzinfo

# Load basic variables
VERSION, COMMIT, DEBUG = env('VERSION', 'unknown'), env('COMMIT', 'unknown'), bool(env('DEBUG', False))

# Database connection
db = create_engine(str(env('DATABASE', 'sqlite:///db.sqlite')))
db_init(db), migrate(db)

# Load DLS variables (all prefixed with "INSTANCE_*" is used as "SERVICE_INSTANCE_*" or "SI_*" in official dls service)
DLS_URL = str(env('DLS_URL', 'localhost'))
DLS_PORT = int(env('DLS_PORT', '443'))
SITE_KEY_XID = str(env('SITE_KEY_XID', '00000000-0000-0000-0000-000000000000'))
INSTANCE_REF = str(env('INSTANCE_REF', '10000000-0000-0000-0000-000000000001'))
ALLOTMENT_REF = str(env('ALLOTMENT_REF', '20000000-0000-0000-0000-000000000001'))
INSTANCE_KEY_RSA = PrivateKey.from_file(str(env('INSTANCE_KEY_RSA', join(dirname(__file__), 'cert/instance.private.pem'))))
INSTANCE_KEY_PUB = PublicKey.from_file(str(env('INSTANCE_KEY_PUB', join(dirname(__file__), 'cert/instance.public.pem'))))
TOKEN_EXPIRE_DELTA = relativedelta(days=int(env('TOKEN_EXPIRE_DAYS', 1)), hours=int(env('TOKEN_EXPIRE_HOURS', 0)))
LEASE_EXPIRE_DELTA = relativedelta(days=int(env('LEASE_EXPIRE_DAYS', 90)), hours=int(env('LEASE_EXPIRE_HOURS', 0)))
LEASE_RENEWAL_PERIOD = float(env('LEASE_RENEWAL_PERIOD', 0.15))
LEASE_RENEWAL_DELTA = timedelta(days=int(env('LEASE_EXPIRE_DAYS', 90)), hours=int(env('LEASE_EXPIRE_HOURS', 0)))
CLIENT_TOKEN_EXPIRE_DELTA = relativedelta(years=12)
CORS_ORIGINS = str(env('CORS_ORIGINS', '')).split(',') if (env('CORS_ORIGINS')) else [f'https://{DLS_URL}']
DT_FORMAT = '%Y-%m-%dT%H:%M:%S.%fZ'
PRODUCT_MAPPING = ProductMapping(filename=join(dirname(__file__), 'static/product_mapping.json'))


jwt_encode_key = jwk.construct(INSTANCE_KEY_RSA.pem(), algorithm=ALGORITHMS.RS256)
jwt_decode_key = jwk.construct(INSTANCE_KEY_PUB.pem(), algorithm=ALGORITHMS.RS256)

# Logging
LOG_LEVEL = logging.DEBUG if DEBUG else logging.INFO
logging.basicConfig(format='[{levelname:^7}] [{module:^15}] {message}', style='{')
logger = logging.getLogger(__name__)
logger.setLevel(LOG_LEVEL)
logging.getLogger('util').setLevel(LOG_LEVEL)
logging.getLogger('NV').setLevel(LOG_LEVEL)


# FastAPI
@asynccontextmanager
async def lifespan(_: FastAPI):
    # on startup
    logger.info(f'''
    
    Using timezone: {str(TZ)}. Make sure this is correct and match your clients!
    
    Your clients renew their license every {str(Lease.calculate_renewal(LEASE_RENEWAL_PERIOD, LEASE_RENEWAL_DELTA))}.
    If the renewal fails, the license is {str(LEASE_RENEWAL_DELTA)} valid.
    
    Your client-token file (.tok) is valid for {str(CLIENT_TOKEN_EXPIRE_DELTA)}.
    ''')

    logger.info(f'Debug is {"enabled" if DEBUG else "disabled"}.')

    yield

    # on shutdown
    logger.info(f'Shutting down ...')


config = dict(openapi_url=None, docs_url=None, redoc_url=None)  # dict(openapi_url='/-/openapi.json', docs_url='/-/docs', redoc_url='/-/redoc')
app = FastAPI(title='FastAPI-DLS', description='Minimal Delegated License Service (DLS).', version=VERSION, lifespan=lifespan, **config)

app.debug = DEBUG
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)


# Helper
def __get_token(request: Request) -> dict:
    authorization_header = request.headers.get('authorization')
    token = authorization_header.split(' ')[1]
    return jwt.decode(token=token, key=jwt_decode_key, algorithms=ALGORITHMS.RS256, options={'verify_aud': False})


# Endpoints

@app.get('/', summary='Index')
async def index():
    return RedirectResponse('/-/readme')


@app.get('/-/', summary='* Index')
async def _index():
    return RedirectResponse('/-/readme')


@app.get('/-/health', summary='* Health')
async def _health():
    return JSONr({'status': 'up'})


@app.get('/-/config', summary='* Config', description='returns environment variables.')
async def _config():
    return JSONr({
        'VERSION': str(VERSION),
        'COMMIT': str(COMMIT),
        'DEBUG': str(DEBUG),
        'DLS_URL': str(DLS_URL),
        'DLS_PORT': str(DLS_PORT),
        'SITE_KEY_XID': str(SITE_KEY_XID),
        'INSTANCE_REF': str(INSTANCE_REF),
        'ALLOTMENT_REF': [str(ALLOTMENT_REF)],
        'TOKEN_EXPIRE_DELTA': str(TOKEN_EXPIRE_DELTA),
        'LEASE_EXPIRE_DELTA': str(LEASE_EXPIRE_DELTA),
        'LEASE_RENEWAL_PERIOD': str(LEASE_RENEWAL_PERIOD),
        'CORS_ORIGINS': str(CORS_ORIGINS),
        'TZ': str(TZ),
    })


@app.get('/-/readme', summary='* Readme')
async def _readme():
    from markdown import markdown
    content = load_file(join(dirname(__file__), '../README.md')).decode('utf-8')
    return HTMLr(markdown(text=content, extensions=['tables', 'fenced_code', 'md_in_html', 'nl2br', 'toc']))


@app.get('/-/manage', summary='* Management UI')
async def _manage(request: Request):
    response = '''
    <!DOCTYPE html>
    <html>
        <head>
            <title>FastAPI-DLS Management</title>
        </head>
        <body>
            <button onclick="deleteOrigins()">delete ALL origins and their leases</button>
            <button onclick="deleteLease()">delete specific lease</button>
            
            <script>
                function deleteOrigins() {
                    const response = confirm('Are you sure you want to delete all origins and their leases?');

                    if (response) {
                        var xhr = new XMLHttpRequest();
                        xhr.open("DELETE", '/-/origins', true);
                        xhr.send();
                    }
                }
                function deleteLease(lease_ref) {
                    if(lease_ref === undefined)
                        lease_ref = window.prompt("Please enter 'lease_ref' which should be deleted");
                    if(lease_ref === null || lease_ref === "")
                        return
                    var xhr = new XMLHttpRequest();
                    xhr.open("DELETE", `/-/lease/${lease_ref}`, true);
                    xhr.send();
                }
            </script>
        </body>
    </html>
    '''
    return HTMLr(response)


@app.get('/-/origins', summary='* Origins')
async def _origins(request: Request, leases: bool = False):
    session = sessionmaker(bind=db)()
    response = []
    for origin in session.query(Origin).all():
        x = origin.serialize()
        if leases:
            serialize = dict(renewal_period=LEASE_RENEWAL_PERIOD, renewal_delta=LEASE_RENEWAL_DELTA)
            x['leases'] = list(map(lambda _: _.serialize(**serialize), Lease.find_by_origin_ref(db, origin.origin_ref)))
        response.append(x)
    session.close()
    return JSONr(response)


@app.delete('/-/origins', summary='* Origins')
async def _origins_delete(request: Request):
    Origin.delete(db)
    return Response(status_code=201)


@app.get('/-/leases', summary='* Leases')
async def _leases(request: Request, origin: bool = False):
    session = sessionmaker(bind=db)()
    response = []
    for lease in session.query(Lease).all():
        serialize = dict(renewal_period=LEASE_RENEWAL_PERIOD, renewal_delta=LEASE_RENEWAL_DELTA)
        x = lease.serialize(**serialize)
        if origin:
            lease_origin = session.query(Origin).filter(Origin.origin_ref == lease.origin_ref).first()
            if lease_origin is not None:
                x['origin'] = lease_origin.serialize()
        response.append(x)
    session.close()
    return JSONr(response)


@app.delete('/-/leases/expired', summary='* Leases')
async def _lease_delete_expired(request: Request):
    Lease.delete_expired(db)
    return Response(status_code=201)


@app.delete('/-/lease/{lease_ref}', summary='* Lease')
async def _lease_delete(request: Request, lease_ref: str):
    if Lease.delete(db, lease_ref) == 1:
        return Response(status_code=201)
    return JSONr(status_code=404, content={'status': 404, 'detail': 'lease not found'})


# venv/lib/python3.9/site-packages/nls_core_service_instance/service_instance_token_manager.py
@app.get('/-/client-token', summary='* Client-Token', description='creates a new messenger token for this service instance')
async def _client_token():
    cur_time = datetime.now(UTC)
    exp_time = cur_time + CLIENT_TOKEN_EXPIRE_DELTA

    payload = {
        "jti": str(uuid4()),
        "iss": "NLS Service Instance",
        "aud": "NLS Licensed Client",
        "iat": timegm(cur_time.timetuple()),
        "nbf": timegm(cur_time.timetuple()),
        "exp": timegm(exp_time.timetuple()),
        "protocol_version": "2.0",
        "update_mode": "ABSOLUTE",
        "scope_ref_list": [ALLOTMENT_REF],
        "fulfillment_class_ref_list": [],
        "service_instance_configuration": {
            "nls_service_instance_ref": INSTANCE_REF,
            "svc_port_set_list": [
                {
                    "idx": 0,
                    "d_name": "DLS",
                    "svc_port_map": [{"service": "auth", "port": DLS_PORT}, {"service": "lease", "port": DLS_PORT}]
                }
            ],
            "node_url_list": [{"idx": 0, "url": DLS_URL, "url_qr": DLS_URL, "svc_port_set_idx": 0}]
        },
        "service_instance_public_key_configuration": {
            "service_instance_public_key_me": {
                "mod": hex(INSTANCE_KEY_PUB.raw().public_numbers().n)[2:],
                "exp": int(INSTANCE_KEY_PUB.raw().public_numbers().e),
            },
            "service_instance_public_key_pem": INSTANCE_KEY_PUB.pem().decode('utf-8'),
            "key_retention_mode": "LATEST_ONLY"
        },
    }

    content = jws.sign(payload, key=jwt_encode_key, headers=None, algorithm=ALGORITHMS.RS256)

    response = StreamingResponse(iter([content]), media_type="text/plain")
    filename = f'client_configuration_token_{datetime.now().strftime("%d-%m-%y-%H-%M-%S")}.tok'
    response.headers["Content-Disposition"] = f'attachment; filename={filename}'

    return response


# venv/lib/python3.9/site-packages/nls_services_auth/test/test_origins_controller.py
@app.post('/auth/v1/origin', description='find or create an origin')
async def auth_v1_origin(request: Request):
    j, cur_time = json_loads((await request.body()).decode('utf-8')), datetime.now(UTC)

    origin_ref = j.get('candidate_origin_ref')
    logger.info(f'> [  origin  ]: {origin_ref}: {j}')

    data = Origin(
        origin_ref=origin_ref,
        hostname=j.get('environment').get('hostname'),
        guest_driver_version=j.get('environment').get('guest_driver_version'),
        os_platform=j.get('environment').get('os_platform'), os_version=j.get('environment').get('os_version'),
    )

    Origin.create_or_update(db, data)

    environment = {
        'raw_env': j.get('environment')
    }
    environment.update(j.get('environment'))

    response = {
        "origin_ref": origin_ref,
        "environment": environment,
        "svc_port_set_list": None,
        "node_url_list": None,
        "node_query_order": None,
        "prompts": None,
        "sync_timestamp": cur_time.strftime(DT_FORMAT)
    }

    return JSONr(response)


# venv/lib/python3.9/site-packages/nls_services_auth/test/test_origins_controller.py
@app.post('/auth/v1/origin/update', description='update an origin evidence')
async def auth_v1_origin_update(request: Request):
    j, cur_time = json_loads((await request.body()).decode('utf-8')), datetime.now(UTC)

    origin_ref = j.get('origin_ref')
    logger.info(f'> [  update  ]: {origin_ref}: {j}')

    data = Origin(
        origin_ref=origin_ref,
        hostname=j.get('environment').get('hostname'),
        guest_driver_version=j.get('environment').get('guest_driver_version'),
        os_platform=j.get('environment').get('os_platform'), os_version=j.get('environment').get('os_version'),
    )

    Origin.create_or_update(db, data)

    response = {
        "environment": j.get('environment'),
        "prompts": None,
        "sync_timestamp": cur_time.strftime(DT_FORMAT)
    }

    return JSONr(response)


# venv/lib/python3.9/site-packages/nls_services_auth/test/test_auth_controller.py
# venv/lib/python3.9/site-packages/nls_core_auth/auth.py - CodeResponse
@app.post('/auth/v1/code', description='get an authorization code')
async def auth_v1_code(request: Request):
    j, cur_time = json_loads((await request.body()).decode('utf-8')), datetime.now(UTC)

    origin_ref = j.get('origin_ref')
    logger.info(f'> [   code   ]: {origin_ref}: {j}')

    delta = relativedelta(minutes=15)
    expires = cur_time + delta

    payload = {
        'iat': timegm(cur_time.timetuple()),
        'exp': timegm(expires.timetuple()),
        'challenge': j.get('code_challenge'),
        'origin_ref': j.get('origin_ref'),
        'key_ref': SITE_KEY_XID,
        'kid': SITE_KEY_XID
    }

    auth_code = jws.sign(payload, key=jwt_encode_key, headers={'kid': payload.get('kid')}, algorithm=ALGORITHMS.RS256)

    response = {
        "auth_code": auth_code,
        "prompts": None,
        "sync_timestamp": cur_time.strftime(DT_FORMAT),
    }

    return JSONr(response)


# venv/lib/python3.9/site-packages/nls_services_auth/test/test_auth_controller.py
# venv/lib/python3.9/site-packages/nls_core_auth/auth.py - TokenResponse
@app.post('/auth/v1/token', description='exchange auth code and verifier for token')
async def auth_v1_token(request: Request):
    j, cur_time = json_loads((await request.body()).decode('utf-8')), datetime.now(UTC)

    try:
        payload = jwt.decode(token=j.get('auth_code'), key=jwt_decode_key, algorithms=ALGORITHMS.RS256)
    except JWTError as e:
        return JSONr(status_code=400, content={'status': 400, 'title': 'invalid token', 'detail': str(e)})

    origin_ref = payload.get('origin_ref')
    logger.info(f'> [   auth   ]: {origin_ref}: {j}')

    # validate the code challenge
    challenge = b64enc(sha256(j.get('code_verifier').encode('utf-8')).digest()).rstrip(b'=').decode('utf-8')
    if payload.get('challenge') != challenge:
        return JSONr(status_code=401, content={'status': 401, 'detail': 'expected challenge did not match verifier'})

    access_expires_on = cur_time + TOKEN_EXPIRE_DELTA

    new_payload = {
        'iat': timegm(cur_time.timetuple()),
        'nbf': timegm(cur_time.timetuple()),
        'iss': 'https://cls.nvidia.org',
        'aud': 'https://cls.nvidia.org',
        'exp': timegm(access_expires_on.timetuple()),
        'key_ref': SITE_KEY_XID,
        'kid': SITE_KEY_XID,
        'origin_ref': origin_ref,
    }

    auth_token = jwt.encode(new_payload, key=jwt_encode_key, headers={'kid': payload.get('kid')}, algorithm=ALGORITHMS.RS256)

    response = {
        "auth_token": auth_token,
        "expires": access_expires_on.strftime(DT_FORMAT),
        "prompts": None,
        "sync_timestamp": cur_time.strftime(DT_FORMAT),
    }

    return JSONr(response)


# NLS 3.4.0 - venv/lib/python3.12/site-packages/nls_services_lease/test/test_lease_single_controller.py
@app.post('/leasing/v1/config-token', description='request to get config token for lease operations')
async def leasing_v1_config_token(request: Request):
    j, cur_time = json_loads((await request.body()).decode('utf-8')), datetime.now(UTC)

    logger.debug(f'CALLED /leasing/v1/config-token')
    logger.debug(f'Headers: {request.headers}')
    logger.debug(f'Request: {j}')

    # todo: THIS IS A DEMO ONLY

    ###
    #
    # https://git.collinwebdesigns.de/nvidia/nls/-/blob/main/src/test/test_config_token.py
    #
    ###

    root_private_key_filename = join(dirname(__file__), 'cert/my_demo_root_private_key.pem')
    root_certificate_filename = join(dirname(__file__), 'cert/my_demo_root_certificate.pem')
    ca_private_key_filename = join(dirname(__file__), 'cert/my_demo_ca_private_key.pem')
    ca_certificate_filename = join(dirname(__file__), 'cert/my_demo_ca_certificate.pem')
    si_private_key_filename = join(dirname(__file__), 'cert/my_demo_si_private_key.pem')
    si_certificate_filename = join(dirname(__file__), 'cert/my_demo_si_certificate.pem')

    def init_config_token_demo():
        from cryptography import x509
        from cryptography.hazmat._oid import NameOID
        from cryptography.hazmat.primitives import serialization, hashes
        from cryptography.hazmat.primitives.asymmetric.rsa import generate_private_key
        from cryptography.hazmat.primitives.serialization import Encoding

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

        with open(root_private_key_filename, 'wb') as f:
            f.write(my_root_private_key_as_pem)

        with open(root_certificate_filename, 'wb') as f:
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
            .add_extension(x509.KeyUsage(digital_signature=False, key_encipherment=False, key_cert_sign=True,
                                         key_agreement=False, content_commitment=False, data_encipherment=False,
                                         crl_sign=True, encipher_only=False, decipher_only=False), critical=True)
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

        with open(ca_private_key_filename, 'wb') as f:
            f.write(my_ca_private_key_as_pem)

        with open(ca_certificate_filename, 'wb') as f:
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

        with open(si_private_key_filename, 'wb') as f:
            f.write(my_si_private_key_as_pem)

        # with open('instance.public.pem', 'wb') as f:
        #   f.write(my_si_public_key_as_pem)

        # create si-certificate subject
        my_si_subject = x509.Name([
            # x509.NameAttribute(NameOID.COMMON_NAME, INSTANCE_REF),
            x509.NameAttribute(NameOID.COMMON_NAME, j.get('service_instance_ref')),
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
                x509.DNSName(j.get('service_instance_ref'))
            ]), critical=False)
            .sign(my_ca_private_key, hashes.SHA256()))

        my_si_public_key_exp = my_si_certificate.public_key().public_numbers().e
        my_si_public_key_mod = f'{my_si_certificate.public_key().public_numbers().n:x}'  # hex value without "0x" prefix

        with open(si_certificate_filename, 'wb') as f:
            f.write(my_si_certificate.public_bytes(encoding=Encoding.PEM))

    if not (isfile(root_private_key_filename)
            and isfile(ca_private_key_filename)
            and isfile(ca_certificate_filename)
            and isfile(si_private_key_filename)
            and isfile(si_certificate_filename)):
        init_config_token_demo()

    my_ca_certificate = Cert.from_file(ca_certificate_filename)
    my_si_certificate = Cert.from_file(si_certificate_filename)
    my_si_private_key = PrivateKey.from_file(si_private_key_filename)
    my_si_private_key_as_pem = my_si_private_key.pem()
    my_si_public_key = my_si_private_key.public_key().raw()
    my_si_public_key_as_pem = my_si_private_key.public_key().pem()

    """ build out payload """

    cur_time = datetime.now(UTC)
    exp_time = cur_time + CLIENT_TOKEN_EXPIRE_DELTA

    payload = {
        "iss": "NLS Service Instance",
        "aud": "NLS Licensed Client",
        "iat": timegm(cur_time.timetuple()),
        "nbf": timegm(cur_time.timetuple()),
        "exp": timegm(exp_time.timetuple()),
        "protocol_version": "2.0",
        "d_name": "DLS",
        "service_instance_ref": j.get('service_instance_ref'),
        "service_instance_public_key_configuration": {
            "service_instance_public_key_me": {
                "mod": hex(my_si_public_key.public_numbers().n)[2:],
                "exp": int(my_si_public_key.public_numbers().e),
            },
            # 64 chars per line (pem default)
            "service_instance_public_key_pem": my_si_public_key_as_pem.decode('utf-8').strip(),
            "key_retention_mode": "LATEST_ONLY"
        },
    }

    my_jwt_encode_key = jwk.construct(my_si_private_key_as_pem.decode('utf-8'), algorithm=ALGORITHMS.RS256)
    config_token = jws.sign(payload, key=my_jwt_encode_key, headers=None, algorithm=ALGORITHMS.RS256)

    response_ca_chain = my_ca_certificate.pem().decode('utf-8')
    response_si_certificate = my_si_certificate.pem().decode('utf-8')

    response = {
        "certificateConfiguration": {
            # 76 chars per line
            "caChain": [response_ca_chain],
            # 76 chars per line
            "publicCert": response_si_certificate,
            "publicKey": {
                "exp": int(my_si_certificate.raw().public_key().public_numbers().e),
                "mod": [hex(my_si_certificate.raw().public_key().public_numbers().n)[2:]],
            },
        },
        "configToken": config_token,
    }

    logging.debug(response)

    return JSONr(response, status_code=200)


# venv/lib/python3.9/site-packages/nls_services_lease/test/test_lease_multi_controller.py
@app.post('/leasing/v1/lessor', description='request multiple leases (borrow) for current origin')
async def leasing_v1_lessor(request: Request):
    j, token, cur_time = json_loads((await request.body()).decode('utf-8')), __get_token(request), datetime.now(UTC)

    logger.debug(j)
    logger.debug(request.headers)

    try:
        token = __get_token(request)
    except JWTError:
        return JSONr(status_code=401, content={'status': 401, 'detail': 'token is not valid'})

    origin_ref = token.get('origin_ref')
    scope_ref_list = j.get('scope_ref_list')
    lease_proposal_list = j.get('lease_proposal_list')
    logger.info(f'> [  create  ]: {origin_ref}: create leases for scope_ref_list {scope_ref_list}')

    for scope_ref in scope_ref_list:
        # if scope_ref not in [ALLOTMENT_REF]:
        #     return JSONr(status_code=500, detail=f'no service instances found for scopes: ["{scope_ref}"]')
        pass

    lease_result_list = []
    for lease_proposal in lease_proposal_list:
        lease_ref = str(uuid4())
        expires = cur_time + LEASE_EXPIRE_DELTA

        product_name = lease_proposal.get('product').get('name')
        feature_name = PRODUCT_MAPPING.get_feature_name(product_name=product_name)

        lease_result_list.append({
            "error": None,
            # https://docs.nvidia.com/license-system/latest/nvidia-license-system-user-guide/index.html
            "lease": {
                "created": cur_time.strftime(DT_FORMAT),
                "expires": expires.strftime(DT_FORMAT),  # todo: lease_proposal.get('duration') => "P0Y0M0DT12H0M0S
                "feature_name": feature_name,
                "lease_intent_id": None,
                "license_type": "CONCURRENT_COUNTED_SINGLE",
                "metadata": None,
                "offline_lease": False,  # todo
                "product_name": product_name,
                "recommended_lease_renewal": LEASE_RENEWAL_PERIOD,
                "ref": lease_ref,
            },
            "ordinal": None,
        })

        data = Lease(origin_ref=origin_ref, lease_ref=lease_ref, lease_created=cur_time, lease_expires=expires)
        Lease.create_or_update(db, data)

    response = {
        "client_challenge": j.get('client_challenge'),
        "lease_result_list": lease_result_list,
        "prompts": None,
        "result_code": None,
        "sync_timestamp": cur_time.strftime(DT_FORMAT),
    }

    logger.debug(response)

    signature = f'b\'{randbytes(256).hex()}\''
    return JSONr(response, headers={'access-control-expose-headers': 'X-NLS-Signature', 'X-NLS-Signature': signature})


# venv/lib/python3.9/site-packages/nls_services_lease/test/test_lease_multi_controller.py
# venv/lib/python3.9/site-packages/nls_dal_service_instance_dls/schema/service_instance/V1_0_21__product_mapping.sql
@app.get('/leasing/v1/lessor/leases', description='get active leases for current origin')
async def leasing_v1_lessor_lease(request: Request):
    token, cur_time = __get_token(request), datetime.now(UTC)

    origin_ref = token.get('origin_ref')

    active_lease_list = list(map(lambda x: x.lease_ref, Lease.find_by_origin_ref(db, origin_ref)))
    logger.info(f'> [  leases  ]: {origin_ref}: found {len(active_lease_list)} active leases')

    response = {
        "active_lease_list": active_lease_list,
        "prompts": None,
        "sync_timestamp": cur_time.strftime(DT_FORMAT),
    }

    return JSONr(response)


# venv/lib/python3.9/site-packages/nls_services_lease/test/test_lease_single_controller.py
# venv/lib/python3.9/site-packages/nls_core_lease/lease_single.py
@app.put('/leasing/v1/lease/{lease_ref}', description='renew a lease')
async def leasing_v1_lease_renew(request: Request, lease_ref: str):
    j, token, cur_time = json_loads((await request.body()).decode('utf-8')), __get_token(request), datetime.now(UTC)

    origin_ref = token.get('origin_ref')
    logger.info(f'> [  renew   ]: {origin_ref}: renew {lease_ref}')

    entity = Lease.find_by_origin_ref_and_lease_ref(db, origin_ref, lease_ref)
    if entity is None:
        return JSONr(status_code=404, content={'status': 404, 'detail': 'requested lease not available'})

    expires = cur_time + LEASE_EXPIRE_DELTA
    response = {
        "client_challenge": j.get('client_challenge'),
        "expires": expires.strftime(DT_FORMAT),
        "feature_expired": False,
        "lease_ref": lease_ref,
        "metadata": None,
        "offline_lease": True,
        "prompts": None,
        "recommended_lease_renewal": LEASE_RENEWAL_PERIOD,
        "sync_timestamp": cur_time.strftime(DT_FORMAT),
    }

    Lease.renew(db, entity, expires, cur_time)

    signature = f'b\'{randbytes(256).hex()}\''
    return JSONr(response, headers={'access-control-expose-headers': 'X-NLS-Signature', 'X-NLS-Signature': signature})


# venv/lib/python3.9/site-packages/nls_services_lease/test/test_lease_single_controller.py
@app.delete('/leasing/v1/lease/{lease_ref}', description='release (return) a lease')
async def leasing_v1_lease_delete(request: Request, lease_ref: str):
    token, cur_time = __get_token(request), datetime.now(UTC)

    origin_ref = token.get('origin_ref')
    logger.info(f'> [  return  ]: {origin_ref}: return {lease_ref}')

    entity = Lease.find_by_lease_ref(db, lease_ref)
    if entity.origin_ref != origin_ref:
        return JSONr(status_code=403, content={'status': 403, 'detail': 'access or operation forbidden'})
    if entity is None:
        return JSONr(status_code=404, content={'status': 404, 'detail': 'requested lease not available'})

    if Lease.delete(db, lease_ref) == 0:
        return JSONr(status_code=404, content={'status': 404, 'detail': 'lease not found'})

    response = {
        "client_challenge": None,
        "lease_ref": lease_ref,
        "prompts": None,
        "sync_timestamp": cur_time.strftime(DT_FORMAT),
    }

    return JSONr(response)


# venv/lib/python3.9/site-packages/nls_services_lease/test/test_lease_multi_controller.py
@app.delete('/leasing/v1/lessor/leases', description='release all leases')
async def leasing_v1_lessor_lease_remove(request: Request):
    token, cur_time = __get_token(request), datetime.now(UTC)

    origin_ref = token.get('origin_ref')

    released_lease_list = list(map(lambda x: x.lease_ref, Lease.find_by_origin_ref(db, origin_ref)))
    deletions = Lease.cleanup(db, origin_ref)
    logger.info(f'> [  remove  ]: {origin_ref}: removed {deletions} leases')

    response = {
        "released_lease_list": released_lease_list,
        "release_failure_list": None,
        "prompts": None,
        "sync_timestamp": cur_time.strftime(DT_FORMAT),
    }

    return JSONr(response)


@app.post('/leasing/v1/lessor/shutdown', description='shutdown all leases')
async def leasing_v1_lessor_shutdown(request: Request):
    j, cur_time = json_loads((await request.body()).decode('utf-8')), datetime.now(UTC)

    token = j.get('token')
    token = jwt.decode(token=token, key=jwt_decode_key, algorithms=ALGORITHMS.RS256, options={'verify_aud': False})
    origin_ref = token.get('origin_ref')

    released_lease_list = list(map(lambda x: x.lease_ref, Lease.find_by_origin_ref(db, origin_ref)))
    deletions = Lease.cleanup(db, origin_ref)
    logger.info(f'> [ shutdown ]: {origin_ref}: removed {deletions} leases')

    response = {
        "released_lease_list": released_lease_list,
        "release_failure_list": None,
        "prompts": None,
        "sync_timestamp": cur_time.strftime(DT_FORMAT),
    }

    return JSONr(response)


if __name__ == '__main__':
    import uvicorn

    ###
    #
    # Running `python app/main.py` assumes that the user created a keypair, e.g. with openssl.
    #
    # openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout app/cert/webserver.key -out app/cert/webserver.crt
    #
    ###

    logger.info(f'> Starting dev-server ...')

    ssl_keyfile = join(dirname(__file__), 'cert/webserver.key')
    ssl_certfile = join(dirname(__file__), 'cert/webserver.crt')

    uvicorn.run('main:app', host='0.0.0.0', port=443, ssl_keyfile=ssl_keyfile, ssl_certfile=ssl_certfile, reload=True)
