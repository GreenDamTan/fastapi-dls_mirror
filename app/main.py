import logging
from base64 import b64encode as b64enc
from calendar import timegm
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, UTC
from hashlib import sha256
from json import loads as json_loads
from os import getenv as env
from os.path import join, dirname
from uuid import uuid4

from dateutil.relativedelta import relativedelta
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.requests import Request
from jose import jws, jwk, jwt, JWTError
from jose.constants import ALGORITHMS
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import StreamingResponse, JSONResponse, Response, RedirectResponse
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import StreamingResponse, JSONResponse as JSONr, HTMLResponse as HTMLr, Response, RedirectResponse
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates

from orm import Origin, Lease, init as db_init, migrate
from util import PrivateKey, PublicKey, load_file

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
app.mount('/static', StaticFiles(directory='static', html=True), name='static'),
templates = Jinja2Templates(directory='templates')

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

@app.get('/', summary='* Index')
async def index():
    return RedirectResponse('/-/')


@app.get('/-/', summary='* Index')
async def _index(request: Request):
    return templates.TemplateResponse(name='views/index.html', context={'request': request, 'VERSION': VERSION})


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
async def _readme(request: Request):
    from markdown import markdown
    content = load_file(join(dirname(__file__), '../README.md')).decode('utf-8')
    markdown = markdown(text=content, extensions=['tables', 'fenced_code', 'md_in_html', 'nl2br', 'toc'])
    context = {'request': request, 'markdown': markdown, 'VERSION': VERSION}
    return templates.TemplateResponse(name='views/dashboard_readme.html', context=context)


@app.get('/-/manage', summary='* Management UI')
async def _manage(request: Request):
    return templates.TemplateResponse(name='views/manage.html', context={'request': request, 'VERSION': VERSION})


@app.get('/-/dashboard', summary='* Dashboard')
async def _dashboard(request: Request):
    return templates.TemplateResponse(name='views/dashboard.html', context={'request': request, 'VERSION': VERSION})


@app.get('/-/dashboard/origins', summary='* Dashboard - Origins')
async def _dashboard_origins(request: Request):
    return templates.TemplateResponse(name='views/dashboard_origins.html', context={'request': request, 'VERSION': VERSION})


@app.get('/-/dashboard/leases', summary='* Dashboard - Leases')
async def _dashboard_origins(request: Request):
    return templates.TemplateResponse(name='views/dashboard_leases.html', context={'request': request, 'VERSION': VERSION})


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


@app.delete('/-/origins/{origin_ref}', summary='* Origins')
async def _origins_delete_origin_ref(request: Request, origin_ref: str):
    if Origin.delete(db, origin_ref) == 1:
        return Response(status_code=201)
    raise JSONResponse(status_code=404, content={'status': 404, 'detail': 'lease not found'})


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

    response = {
        "origin_ref": origin_ref,
        "environment": j.get('environment'),
        "svc_port_set_list": None,
        "node_url_list": None,
        "node_query_order": None,
        "prompts": None,
        "sync_timestamp": cur_time.isoformat()
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
        "sync_timestamp": cur_time.isoformat()
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
        "sync_timestamp": cur_time.isoformat(),
        "prompts": None
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
        'origin_ref': origin_ref,
        'key_ref': SITE_KEY_XID,
        'kid': SITE_KEY_XID,
    }

    auth_token = jwt.encode(new_payload, key=jwt_encode_key, headers={'kid': payload.get('kid')}, algorithm=ALGORITHMS.RS256)

    response = {
        "expires": access_expires_on.isoformat(),
        "auth_token": auth_token,
        "sync_timestamp": cur_time.isoformat(),
    }

    return JSONr(response)


# venv/lib/python3.9/site-packages/nls_services_lease/test/test_lease_multi_controller.py
@app.post('/leasing/v1/lessor', description='request multiple leases (borrow) for current origin')
async def leasing_v1_lessor(request: Request):
    j, token, cur_time = json_loads((await request.body()).decode('utf-8')), __get_token(request), datetime.now(UTC)

    try:
        token = __get_token(request)
    except JWTError:
        return JSONr(status_code=401, content={'status': 401, 'detail': 'token is not valid'})

    origin_ref = token.get('origin_ref')
    scope_ref_list = j.get('scope_ref_list')
    logger.info(f'> [  create  ]: {origin_ref}: create leases for scope_ref_list {scope_ref_list}')

    lease_result_list = []
    for scope_ref in scope_ref_list:
        # if scope_ref not in [ALLOTMENT_REF]:
        #     return JSONr(status_code=500, detail=f'no service instances found for scopes: ["{scope_ref}"]')

        lease_ref = str(uuid4())
        expires = cur_time + LEASE_EXPIRE_DELTA
        lease_result_list.append({
            "ordinal": 0,
            # https://docs.nvidia.com/license-system/latest/nvidia-license-system-user-guide/index.html
            "lease": {
                "ref": lease_ref,
                "created": cur_time.isoformat(),
                "expires": expires.isoformat(),
                "recommended_lease_renewal": LEASE_RENEWAL_PERIOD,
                "offline_lease": "true",
                "license_type": "CONCURRENT_COUNTED_SINGLE"
            }
        })

        data = Lease(origin_ref=origin_ref, lease_ref=lease_ref, lease_created=cur_time, lease_expires=expires)
        Lease.create_or_update(db, data)

    response = {
        "lease_result_list": lease_result_list,
        "result_code": "SUCCESS",
        "sync_timestamp": cur_time.isoformat(),
        "prompts": None
    }

    return JSONr(response)


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
        "sync_timestamp": cur_time.isoformat(),
        "prompts": None
    }

    return JSONr(response)


# venv/lib/python3.9/site-packages/nls_services_lease/test/test_lease_single_controller.py
# venv/lib/python3.9/site-packages/nls_core_lease/lease_single.py
@app.put('/leasing/v1/lease/{lease_ref}', description='renew a lease')
async def leasing_v1_lease_renew(request: Request, lease_ref: str):
    token, cur_time = __get_token(request), datetime.now(UTC)

    origin_ref = token.get('origin_ref')
    logger.info(f'> [  renew   ]: {origin_ref}: renew {lease_ref}')

    entity = Lease.find_by_origin_ref_and_lease_ref(db, origin_ref, lease_ref)
    if entity is None:
        return JSONr(status_code=404, content={'status': 404, 'detail': 'requested lease not available'})

    expires = cur_time + LEASE_EXPIRE_DELTA
    response = {
        "lease_ref": lease_ref,
        "expires": expires.isoformat(),
        "recommended_lease_renewal": LEASE_RENEWAL_PERIOD,
        "offline_lease": True,
        "prompts": None,
        "sync_timestamp": cur_time.isoformat(),
    }

    Lease.renew(db, entity, expires, cur_time)

    return JSONr(response)


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
        "lease_ref": lease_ref,
        "prompts": None,
        "sync_timestamp": cur_time.isoformat(),
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
        "sync_timestamp": cur_time.isoformat(),
        "prompts": None
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
        "sync_timestamp": cur_time.isoformat(),
        "prompts": None
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
