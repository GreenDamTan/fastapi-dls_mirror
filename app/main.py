from base64 import b64encode
from hashlib import sha256
from uuid import uuid4
from os.path import join, dirname
from os import getenv
from fastapi import FastAPI, HTTPException
from fastapi.requests import Request
import json
from datetime import datetime
from dateutil.relativedelta import relativedelta
from calendar import timegm
from jose import jws, jwk, jwt
from jose.constants import ALGORITHMS
from starlette.responses import StreamingResponse, JSONResponse

from helper import load_key, private_bytes, public_key

# todo: initialize certificate (or should be done by user, and passed through "volumes"?)

app = FastAPI()

LEASE_EXPIRE_DELTA = relativedelta(minutes=15)  # days=90

DLS_URL = str(getenv('DLS_URL', 'localhost'))
DLS_PORT = int(getenv('DLS_PORT', '443'))
SITE_KEY_XID = getenv('SITE_KEY_XID', '00000000-0000-0000-0000-000000000000')
INSTANCE_KEY_RSA = load_key(join(dirname(__file__), 'cert/instance.private.pem'))
INSTANCE_KEY_PUB = load_key(join(dirname(__file__), 'cert/instance.public.pem'))


@app.get('/')
async def index():
    return JSONResponse({'hello': 'world'})


@app.get('/status')
async def status(request: Request):
    return JSONResponse({'status': 'up'})


# venv/lib/python3.9/site-packages/nls_core_service_instance/service_instance_token_manager.py
@app.get('/client-token')
async def client_token():
    cur_time = datetime.utcnow()
    exp_time = cur_time + relativedelta(years=12)

    service_instance_public_key_configuration = {
        "service_instance_public_key_me": {
            "mod": hex(INSTANCE_KEY_PUB.public_key().n)[2:],
            "exp": INSTANCE_KEY_PUB.public_key().e,
        },
        "service_instance_public_key_pem": INSTANCE_KEY_PUB.export_key().decode('utf-8'),
        "key_retention_mode": "LATEST_ONLY"
    }

    payload = {
        "jti": str(uuid4()),
        "iss": "NLS Service Instance",
        "aud": "NLS Licensed Client",
        "iat": timegm(cur_time.timetuple()),
        "nbf": timegm(cur_time.timetuple()),
        "exp": timegm(exp_time.timetuple()),
        "update_mode": "ABSOLUTE",
        "scope_ref_list": [str(uuid4())],
        "fulfillment_class_ref_list": [],
        "service_instance_configuration": {
            "nls_service_instance_ref": "00000000-0000-0000-0000-000000000000",
            "svc_port_set_list": [
                {
                    "idx": 0,
                    "d_name": "DLS",
                    "svc_port_map": [
                        {"service": "auth", "port": DLS_PORT},
                        {"service": "lease", "port": DLS_PORT}
                    ]
                }
            ],
            "node_url_list": [{"idx": 0, "url": DLS_URL, "url_qr": DLS_URL, "svc_port_set_idx": 0}]
        },
        "service_instance_public_key_configuration": service_instance_public_key_configuration,
    }

    key = jwk.construct(INSTANCE_KEY_RSA.export_key().decode('utf-8'), algorithm=ALGORITHMS.RS256)
    data = jws.sign(payload, key=key, headers=None, algorithm='RS256')

    response = StreamingResponse(iter([data]), media_type="text/plain")
    filename = f'client_configuration_token_{datetime.now().strftime("%d-%m-%y-%H-%M-%S")}'
    response.headers["Content-Disposition"] = f'attachment; filename={filename}'
    return response


# venv/lib/python3.9/site-packages/nls_services_auth/test/test_origins_controller.py
@app.post('/auth/v1/origin')
async def auth(request: Request):
    body = await request.body()
    body = body.decode('utf-8')
    j = json.loads(body)
    # {"candidate_origin_ref":"00112233-4455-6677-8899-aabbccddeeff","environment":{"fingerprint":{"mac_address_list":["ff:ff:ff:ff:ff:ff"]},"hostname":"my-hostname","ip_address_list":["192.168.178.123","fe80::","fe80::1%enp6s18"],"guest_driver_version":"510.85.02","os_platform":"Debian GNU/Linux 11 (bullseye) 11","os_version":"11 (bullseye)"},"registration_pending":false,"update_pending":false}
    print(f'> [  origin  ]: {j}')

    cur_time = datetime.utcnow()
    response = {
        "origin_ref": j['candidate_origin_ref'],
        "environment": j['environment'],
        "svc_port_set_list": None,
        "node_url_list": None,
        "node_query_order": None,
        "prompts": None,
        "sync_timestamp": cur_time.isoformat()
    }
    return JSONResponse(response)


# venv/lib/python3.9/site-packages/nls_services_auth/test/test_auth_controller.py
# venv/lib/python3.9/site-packages/nls_core_auth/auth.py - CodeResponse
@app.post('/auth/v1/code')
async def code(request: Request):
    body = await request.body()
    body = body.decode('utf-8')
    j = json.loads(body)
    # {"code_challenge":"...","origin_ref":"00112233-4455-6677-8899-aabbccddeeff"}
    print(f'> [   code   ]: {j}')

    cur_time = datetime.utcnow()
    expires = cur_time + relativedelta(days=1)

    payload = {
        'iat': timegm(cur_time.timetuple()),
        'exp': timegm(expires.timetuple()),
        'challenge': j['code_challenge'],
        'origin_ref': j['code_challenge'],
        'key_ref': SITE_KEY_XID,
        'kid': SITE_KEY_XID
    }

    headers = None
    kid = payload.get('kid')
    if kid:
        headers = {'kid': kid}
    key = jwk.construct(INSTANCE_KEY_RSA.export_key().decode('utf-8'), algorithm=ALGORITHMS.RS512)
    auth_code = jws.sign(payload, key, headers=headers, algorithm='RS256')

    response = {
        "auth_code": auth_code,
        "sync_timestamp": cur_time.isoformat(),
        "prompts": None
    }
    return JSONResponse(response)


# venv/lib/python3.9/site-packages/nls_services_auth/test/test_auth_controller.py
# venv/lib/python3.9/site-packages/nls_core_auth/auth.py - TokenResponse
@app.post('/auth/v1/token')
async def token(request: Request):
    body = await request.body()
    body = body.decode('utf-8')
    j = json.loads(body)
    # {"auth_code":"...","code_verifier":"..."}

    # payload = self._security.get_valid_payload(req.auth_code)  # todo
    key = jwk.construct(INSTANCE_KEY_PUB.export_key().decode('utf-8'), algorithm=ALGORITHMS.RS512)
    payload = jwt.decode(token=j['auth_code'], key=key)

    # validate the code challenge
    if payload['challenge'] != b64encode(sha256(j['code_verifier'].encode('utf-8')).digest()).rstrip(b'=').decode('utf-8'):
        raise HTTPException(status_code=403, detail='expected challenge did not match verifier')

    cur_time = datetime.utcnow()
    access_expires_on = cur_time + relativedelta(days=1)

    new_payload = {
        'iat': timegm(cur_time.timetuple()),
        'nbf': timegm(cur_time.timetuple()),
        'iss': 'https://cls.nvidia.org',
        'aud': 'https://cls.nvidia.org',
        'exp': timegm(access_expires_on.timetuple()),
        'origin_ref': payload['origin_ref'],
        'key_ref': SITE_KEY_XID,
        'kid': SITE_KEY_XID,
    }

    headers = None
    kid = payload.get('kid')
    if kid:
        headers = {'kid': kid}
    key = jwk.construct(INSTANCE_KEY_RSA.export_key().decode('utf-8'), algorithm=ALGORITHMS.RS512)
    auth_token = jwt.encode(new_payload, key=key, headers=headers, algorithm='RS256')

    response = {
        "expires": access_expires_on.isoformat(),
        "auth_token": auth_token,
        "sync_timestamp": cur_time.isoformat(),
    }

    return JSONResponse(response)


@app.post('/leasing/v1/lessor')
async def lessor(request: Request):
    body = await request.body()
    body = body.decode('utf-8')
    j = json.loads(body)
    # {'fulfillment_context': {'fulfillment_class_ref_list': []}, 'lease_proposal_list': [{'license_type_qualifiers': {'count': 1}, 'product': {'name': 'NVIDIA RTX Virtual Workstation'}}], 'proposal_evaluation_mode': 'ALL_OF', 'scope_ref_list': ['00112233-4455-6677-8899-aabbccddeeff']}
    print(f'> [  lessor  ]: {j}')

    cur_time = datetime.utcnow()
    # todo: keep track of leases, to return correct list on '/leasing/v1/lessor/leases'
    lease_result_list = []
    for scope_ref in j['scope_ref_list']:
        lease_result_list.append({
            "ordinal": 0,
            "lease": {
                "ref": scope_ref,
                "created": cur_time.isoformat(),
                "expires": (cur_time + LEASE_EXPIRE_DELTA).isoformat(),
                "recommended_lease_renewal": 0.15,
                "offline_lease": "true",
                "license_type": "CONCURRENT_COUNTED_SINGLE"
            }
        })

    response = {
        "lease_result_list": lease_result_list,
        "result_code": "SUCCESS",
        "sync_timestamp": cur_time.isoformat(),
        "prompts": None
    }

    return JSONResponse(response)


# venv/lib/python3.9/site-packages/nls_services_lease/test/test_lease_multi_controller.py
@app.get('/leasing/v1/lessor/leases')
async def lease(request: Request):
    cur_time = datetime.utcnow()
    # venv/lib/python3.9/site-packages/nls_dal_service_instance_dls/schema/service_instance/V1_0_21__product_mapping.sql
    response = {
        # GRID-Virtual-WS 2.0 CONCURRENT_COUNTED_SINGLE
        "active_lease_list": [
            "BE276D7B-2CDB-11EC-9838-061A22468B59"
        ],
        "sync_timestamp": cur_time.isoformat(),
        "prompts": None
    }

    return JSONResponse(response)


# venv/lib/python3.9/site-packages/nls_core_lease/lease_single.py
@app.put('/leasing/v1/lease/{lease_ref}')
async def lease_renew(request: Request, lease_ref: str):
    print(f'> [  renew   ]: lease: {lease_ref}')

    cur_time = datetime.utcnow()
    response = {
        "lease_ref": lease_ref,
        "expires": (cur_time + LEASE_EXPIRE_DELTA).isoformat(),
        "recommended_lease_renewal": 0.16,
        "offline_lease": True,
        "prompts": None,
        "sync_timestamp": cur_time.isoformat(),
    }

    return JSONResponse(response)


@app.delete('/leasing/v1/lessor/leases')
async def lease_remove(request: Request, status_code=200):
    cur_time = datetime.utcnow()
    response = {
        "released_lease_list": None,
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

    print(f'> Starting dev-server ...')

    ssl_keyfile = join(dirname(__file__), 'cert/webserver.key')
    ssl_certfile = join(dirname(__file__), 'cert/webserver.crt')

    uvicorn.run('main:app', host='0.0.0.0', port=443, ssl_keyfile=ssl_keyfile, ssl_certfile=ssl_certfile, reload=True)
