import logging
from base64 import b64encode as b64enc
from hashlib import sha256
from uuid import uuid4
from os.path import join, dirname
from os import getenv as env

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.requests import Request
import json
from datetime import datetime
from dateutil.relativedelta import relativedelta
from calendar import timegm
from jose import jws, jwk, jwt
from jose.constants import ALGORITHMS
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import StreamingResponse, JSONResponse, HTMLResponse, Response, RedirectResponse
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from util import load_key, load_file
from orm import Origin, Lease, init as db_init, migrate

logger = logging.getLogger()
load_dotenv('../version.env')

VERSION, COMMIT, DEBUG = env('VERSION', 'unknown'), env('COMMIT', 'unknown'), bool(env('DEBUG', False))

config = dict(openapi_url='/-/openapi.json', docs_url='/-/docs', redoc_url='/-/redoc')
app = FastAPI(title='FastAPI-DLS', description='Minimal Delegated License Service (DLS).', version=VERSION, **config)
db = create_engine(str(env('DATABASE', 'sqlite:///db.sqlite')))
db_init(db), migrate(db)

DLS_URL = str(env('DLS_URL', 'localhost'))
DLS_PORT = int(env('DLS_PORT', '443'))
SITE_KEY_XID = str(env('SITE_KEY_XID', '00000000-0000-0000-0000-000000000000'))
INSTANCE_REF = str(env('INSTANCE_REF', '00000000-0000-0000-0000-000000000000'))
INSTANCE_KEY_RSA = load_key(str(env('INSTANCE_KEY_RSA', join(dirname(__file__), 'cert/instance.private.pem'))))
INSTANCE_KEY_PUB = load_key(str(env('INSTANCE_KEY_PUB', join(dirname(__file__), 'cert/instance.public.pem'))))
TOKEN_EXPIRE_DELTA = relativedelta(hours=1)  # days=1
LEASE_EXPIRE_DELTA = relativedelta(days=int(env('LEASE_EXPIRE_DAYS', 90)))
CORS_ORIGINS = str(env('CORS_ORIGINS', '')).split(',') if (env('CORS_ORIGINS')) else [f'https://{DLS_URL}']

jwt_encode_key = jwk.construct(INSTANCE_KEY_RSA.export_key().decode('utf-8'), algorithm=ALGORITHMS.RS256)
jwt_decode_key = jwk.construct(INSTANCE_KEY_PUB.export_key().decode('utf-8'), algorithm=ALGORITHMS.RS256)

app.debug = DEBUG
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

logger.setLevel(logging.DEBUG if DEBUG else logging.INFO)


def __get_token(request: Request) -> dict:
    authorization_header = request.headers.get('authorization')
    token = authorization_header.split(' ')[1]
    return jwt.decode(token=token, key=jwt_decode_key, algorithms=ALGORITHMS.RS256, options={'verify_aud': False})


@app.get('/', summary='Index')
async def index():
    return RedirectResponse('/-/readme')


@app.get('/status', summary='* Status', description='returns current service status, version (incl. git-commit) and some variables.', deprecated=True)
async def status():
    return JSONResponse({'status': 'up', 'version': VERSION, 'commit': COMMIT, 'debug': DEBUG})


@app.get('/-/', summary='* Index')
async def _index():
    return RedirectResponse('/-/readme')


@app.get('/-/health', summary='* Health')
async def _health(request: Request):
    return JSONResponse({'status': 'up', 'version': VERSION, 'commit': COMMIT, 'debug': DEBUG})


@app.get('/-/readme', summary='* Readme')
async def _readme():
    from markdown import markdown
    content = load_file('../README.md').decode('utf-8')
    return HTMLResponse(markdown(text=content, extensions=['tables', 'fenced_code', 'md_in_html', 'nl2br', 'toc']))


@app.get('/-/manage', summary='* Management UI')
async def _manage(request: Request):
    response = '''
    <!DOCTYPE html>
    <html>
        <head>
            <title>FastAPI-DLS Management</title>
        </head>
        <body>
            <button onclick="deleteOrigins()">delete origins and their leases</button>
            <button onclick="deleteLease()">delete specific lease</button>
            
            <script>
                function deleteOrigins() {
                    var xhr = new XMLHttpRequest();
                    xhr.open("DELETE", '/-/origins', true);
                    xhr.send();
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
    return HTMLResponse(response)


@app.get('/-/origins', summary='* Origins')
async def _origins(request: Request, leases: bool = False):
    session = sessionmaker(bind=db)()
    response = []
    for origin in session.query(Origin).all():
        x = origin.serialize()
        if leases:
            x['leases'] = list(map(lambda _: _.serialize(), Lease.find_by_origin_ref(db, origin.origin_ref)))
        response.append(x)
    session.close()
    return JSONResponse(response)


@app.delete('/-/origins', summary='* Origins')
async def _origins_delete(request: Request):
    Origin.delete(db)
    return Response(status_code=201)


@app.get('/-/leases', summary='* Leases')
async def _leases(request: Request, origin: bool = False):
    session = sessionmaker(bind=db)()
    response = []
    for lease in session.query(Lease).all():
        x = lease.serialize()
        if origin:
            # assume that each lease has a valid origin record
            x['origin'] = session.query(Origin).filter(Origin.origin_ref == lease.origin_ref).first().serialize()
        response.append(x)
    session.close()
    return JSONResponse(response)


@app.delete('/-/lease/{lease_ref}', summary='* Lease')
async def _lease_delete(request: Request, lease_ref: str):
    if Lease.delete(db, lease_ref) == 1:
        return Response(status_code=201)
    raise HTTPException(status_code=404, detail='lease not found')


# venv/lib/python3.9/site-packages/nls_core_service_instance/service_instance_token_manager.py
@app.get('/-/client-token', summary='* Client-Token', description='creates a new messenger token for this service instance')
async def _client_token():
    cur_time = datetime.utcnow()
    exp_time = cur_time + relativedelta(years=12)

    payload = {
        "jti": str(uuid4()),
        "iss": "NLS Service Instance",
        "aud": "NLS Licensed Client",
        "iat": timegm(cur_time.timetuple()),
        "nbf": timegm(cur_time.timetuple()),
        "exp": timegm(exp_time.timetuple()),
        "update_mode": "ABSOLUTE",
        "scope_ref_list": [str(uuid4())],  # this is our LEASE_REF
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
                "mod": hex(INSTANCE_KEY_PUB.public_key().n)[2:],
                "exp": int(INSTANCE_KEY_PUB.public_key().e),
            },
            "service_instance_public_key_pem": INSTANCE_KEY_PUB.export_key().decode('utf-8'),
            "key_retention_mode": "LATEST_ONLY"
        },
    }

    content = jws.sign(payload, key=jwt_encode_key, headers=None, algorithm=ALGORITHMS.RS256)

    response = StreamingResponse(iter([content]), media_type="text/plain")
    filename = f'client_configuration_token_{datetime.now().strftime("%d-%m-%y-%H-%M-%S")}.tok'
    response.headers["Content-Disposition"] = f'attachment; filename={filename}'

    return response


@app.get('/client-token', summary='* Client-Token', description='creates a new messenger token for this service instance', deprecated=True)
async def client_token():
    return RedirectResponse('/-/client-token')


# venv/lib/python3.9/site-packages/nls_services_auth/test/test_origins_controller.py
# {"candidate_origin_ref":"00112233-4455-6677-8899-aabbccddeeff","environment":{"fingerprint":{"mac_address_list":["ff:ff:ff:ff:ff:ff"]},"hostname":"my-hostname","ip_address_list":["192.168.178.123","fe80::","fe80::1%enp6s18"],"guest_driver_version":"510.85.02","os_platform":"Debian GNU/Linux 11 (bullseye) 11","os_version":"11 (bullseye)"},"registration_pending":false,"update_pending":false}
@app.post('/auth/v1/origin', description='find or create an origin')
async def auth_v1_origin(request: Request):
    j, cur_time = json.loads((await request.body()).decode('utf-8')), datetime.utcnow()

    origin_ref = j['candidate_origin_ref']
    logging.info(f'> [  origin  ]: {origin_ref}: {j}')

    data = Origin(
        origin_ref=origin_ref,
        hostname=j['environment']['hostname'],
        guest_driver_version=j['environment']['guest_driver_version'],
        os_platform=j['environment']['os_platform'], os_version=j['environment']['os_version'],
    )

    Origin.create_or_update(db, data)

    response = {
        "origin_ref": origin_ref,
        "environment": j['environment'],
        "svc_port_set_list": None,
        "node_url_list": None,
        "node_query_order": None,
        "prompts": None,
        "sync_timestamp": cur_time.isoformat()
    }

    return JSONResponse(response)


# venv/lib/python3.9/site-packages/nls_services_auth/test/test_origins_controller.py
# { "environment" : { "guest_driver_version" : "guest_driver_version", "hostname" : "myhost", "ip_address_list" : [ "192.168.1.129" ], "os_version" : "os_version", "os_platform" : "os_platform", "fingerprint" : { "mac_address_list" : [ "e4:b9:7a:e5:7b:ff" ] }, "host_driver_version" : "host_driver_version" }, "origin_ref" : "00112233-4455-6677-8899-aabbccddeeff" }
@app.post('/auth/v1/origin/update', description='update an origin evidence')
async def auth_v1_origin_update(request: Request):
    j, cur_time = json.loads((await request.body()).decode('utf-8')), datetime.utcnow()

    origin_ref = j['origin_ref']
    logging.info(f'> [  update  ]: {origin_ref}: {j}')

    data = Origin(
        origin_ref=origin_ref,
        hostname=j['environment']['hostname'],
        guest_driver_version=j['environment']['guest_driver_version'],
        os_platform=j['environment']['os_platform'], os_version=j['environment']['os_version'],
    )

    Origin.create_or_update(db, data)

    response = {
        "environment": j['environment'],
        "prompts": None,
        "sync_timestamp": cur_time.isoformat()
    }

    return JSONResponse(response)


# venv/lib/python3.9/site-packages/nls_services_auth/test/test_auth_controller.py
# venv/lib/python3.9/site-packages/nls_core_auth/auth.py - CodeResponse
# {"code_challenge":"...","origin_ref":"00112233-4455-6677-8899-aabbccddeeff"}
@app.post('/auth/v1/code', description='get an authorization code')
async def auth_v1_code(request: Request):
    j, cur_time = json.loads((await request.body()).decode('utf-8')), datetime.utcnow()

    origin_ref = j['origin_ref']
    logging.info(f'> [   code   ]: {origin_ref}: {j}')

    delta = relativedelta(minutes=15)
    expires = cur_time + delta

    payload = {
        'iat': timegm(cur_time.timetuple()),
        'exp': timegm(expires.timetuple()),
        'challenge': j['code_challenge'],
        'origin_ref': j['origin_ref'],
        'key_ref': SITE_KEY_XID,
        'kid': SITE_KEY_XID
    }

    auth_code = jws.sign(payload, key=jwt_encode_key, headers={'kid': payload.get('kid')}, algorithm=ALGORITHMS.RS256)

    response = {
        "auth_code": auth_code,
        "sync_timestamp": cur_time.isoformat(),
        "prompts": None
    }

    return JSONResponse(response)


# venv/lib/python3.9/site-packages/nls_services_auth/test/test_auth_controller.py
# venv/lib/python3.9/site-packages/nls_core_auth/auth.py - TokenResponse
# {"auth_code":"...","code_verifier":"..."}
@app.post('/auth/v1/token', description='exchange auth code and verifier for token')
async def auth_v1_token(request: Request):
    j, cur_time = json.loads((await request.body()).decode('utf-8')), datetime.utcnow()
    payload = jwt.decode(token=j['auth_code'], key=jwt_decode_key)

    origin_ref = payload['origin_ref']
    logging.info(f'> [   auth   ]: {origin_ref}: {j}')

    # validate the code challenge
    if payload['challenge'] != b64enc(sha256(j['code_verifier'].encode('utf-8')).digest()).rstrip(b'=').decode('utf-8'):
        raise HTTPException(status_code=401, detail='expected challenge did not match verifier')

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

    return JSONResponse(response)


# {'fulfillment_context': {'fulfillment_class_ref_list': []}, 'lease_proposal_list': [{'license_type_qualifiers': {'count': 1}, 'product': {'name': 'NVIDIA RTX Virtual Workstation'}}], 'proposal_evaluation_mode': 'ALL_OF', 'scope_ref_list': ['00112233-4455-6677-8899-aabbccddeeff']}
@app.post('/leasing/v1/lessor', description='request multiple leases (borrow) for current origin')
async def leasing_v1_lessor(request: Request):
    j, token, cur_time = json.loads((await request.body()).decode('utf-8')), __get_token(request), datetime.utcnow()

    origin_ref = token.get('origin_ref')
    scope_ref_list = j['scope_ref_list']
    logging.info(f'> [  create  ]: {origin_ref}: create leases for scope_ref_list {scope_ref_list}')

    lease_result_list = []
    for scope_ref in scope_ref_list:
        expires = cur_time + LEASE_EXPIRE_DELTA
        lease_result_list.append({
            "ordinal": 0,
            # https://docs.nvidia.com/license-system/latest/nvidia-license-system-user-guide/index.html
            "lease": {
                "ref": scope_ref,
                "created": cur_time.isoformat(),
                "expires": expires.isoformat(),
                # The percentage of the lease period that must elapse before a licensed client can renew a license
                "recommended_lease_renewal": 0.15,
                "offline_lease": "true",
                "license_type": "CONCURRENT_COUNTED_SINGLE"
            }
        })

        data = Lease(origin_ref=origin_ref, lease_ref=scope_ref, lease_created=cur_time, lease_expires=expires)
        Lease.create_or_update(db, data)

    response = {
        "lease_result_list": lease_result_list,
        "result_code": "SUCCESS",
        "sync_timestamp": cur_time.isoformat(),
        "prompts": None
    }

    return JSONResponse(response)


# venv/lib/python3.9/site-packages/nls_services_lease/test/test_lease_multi_controller.py
# venv/lib/python3.9/site-packages/nls_dal_service_instance_dls/schema/service_instance/V1_0_21__product_mapping.sql
@app.get('/leasing/v1/lessor/leases', description='get active leases for current origin')
async def leasing_v1_lessor_lease(request: Request):
    token, cur_time = __get_token(request), datetime.utcnow()

    origin_ref = token.get('origin_ref')

    active_lease_list = list(map(lambda x: x.lease_ref, Lease.find_by_origin_ref(db, origin_ref)))
    logging.info(f'> [  leases  ]: {origin_ref}: found {len(active_lease_list)} active leases')

    response = {
        "active_lease_list": active_lease_list,
        "sync_timestamp": cur_time.isoformat(),
        "prompts": None
    }

    return JSONResponse(response)


# venv/lib/python3.9/site-packages/nls_core_lease/lease_single.py
@app.put('/leasing/v1/lease/{lease_ref}', description='renew a lease')
async def leasing_v1_lease_renew(request: Request, lease_ref: str):
    token, cur_time = __get_token(request), datetime.utcnow()

    origin_ref = token.get('origin_ref')
    logging.info(f'> [  renew   ]: {origin_ref}: renew {lease_ref}')

    entity = Lease.find_by_origin_ref_and_lease_ref(db, origin_ref, lease_ref)
    if entity is None:
        raise HTTPException(status_code=404, detail='requested lease not available')

    expires = cur_time + LEASE_EXPIRE_DELTA
    response = {
        "lease_ref": lease_ref,
        "expires": expires.isoformat(),
        "recommended_lease_renewal": 0.16,
        "offline_lease": True,
        "prompts": None,
        "sync_timestamp": cur_time.isoformat(),
    }

    Lease.renew(db, entity, expires, cur_time)

    return JSONResponse(response)


@app.delete('/leasing/v1/lease/{lease_ref}', description='release (return) a lease')
async def leasing_v1_lease_delete(request: Request, lease_ref: str):
    token, cur_time = __get_token(request), datetime.utcnow()

    origin_ref = token.get('origin_ref')
    logging.info(f'> [  return  ]: {origin_ref}: return {lease_ref}')

    entity = Lease.find_by_lease_ref(db, lease_ref)
    if entity.origin_ref != origin_ref:
        raise HTTPException(status_code=403, detail='access or operation forbidden')
    if entity is None:
        raise HTTPException(status_code=404, detail='requested lease not available')

    if Lease.delete(db, lease_ref) == 0:
        raise HTTPException(status_code=404, detail='lease not found')

    response = {
        "lease_ref": lease_ref,
        "prompts": None,
        "sync_timestamp": cur_time.isoformat(),
    }

    return JSONResponse(response)


@app.delete('/leasing/v1/lessor/leases', description='release all leases')
async def leasing_v1_lessor_lease_remove(request: Request):
    token, cur_time = __get_token(request), datetime.utcnow()

    origin_ref = token.get('origin_ref')

    released_lease_list = list(map(lambda x: x.lease_ref, Lease.find_by_origin_ref(db, origin_ref)))
    deletions = Lease.cleanup(db, origin_ref)
    logging.info(f'> [  remove  ]: {origin_ref}: removed {deletions} leases')

    response = {
        "released_lease_list": released_lease_list,
        "release_failure_list": None,
        "sync_timestamp": cur_time.isoformat(),
        "prompts": None
    }

    return JSONResponse(response)


if __name__ == '__main__':
    import uvicorn

    ###
    #
    # Running `python app/main.py` assumes that the user created a keypair, e.g. with openssl.
    #
    # openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout app/cert/webserver.key -out app/cert/webserver.crt
    #
    ###

    logging.info(f'> Starting dev-server ...')

    ssl_keyfile = join(dirname(__file__), 'cert/webserver.key')
    ssl_certfile = join(dirname(__file__), 'cert/webserver.crt')

    uvicorn.run('main:app', host='0.0.0.0', port=443, ssl_keyfile=ssl_keyfile, ssl_certfile=ssl_certfile, reload=True)
