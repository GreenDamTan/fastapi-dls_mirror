from base64 import b64encode as b64enc
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
import dataset
from Crypto.PublicKey import RSA
from Crypto.PublicKey.RSA import RsaKey


def load_file(filename) -> bytes:
    with open(filename, 'rb') as file:
        content = file.read()
    return content


def load_key(filename) -> RsaKey:
    return RSA.import_key(extern_key=load_file(filename), passphrase=None)


# todo: initialize certificate (or should be done by user, and passed through "volumes"?)

app, db = FastAPI(), dataset.connect('sqlite:///db.sqlite')

LEASE_EXPIRE_DELTA = relativedelta(minutes=15)  # days=90

DLS_URL = str(getenv('DLS_URL', 'localhost'))
DLS_PORT = int(getenv('DLS_PORT', '443'))
SITE_KEY_XID = getenv('SITE_KEY_XID', '00000000-0000-0000-0000-000000000000')
INSTANCE_KEY_RSA = load_key(join(dirname(__file__), 'cert/instance.private.pem'))
INSTANCE_KEY_PUB = load_key(join(dirname(__file__), 'cert/instance.public.pem'))

jwt_encode_key = jwk.construct(INSTANCE_KEY_RSA.export_key().decode('utf-8'), algorithm=ALGORITHMS.RS256)
jwt_decode_key = jwk.construct(INSTANCE_KEY_PUB.export_key().decode('utf-8'), algorithm=ALGORITHMS.RS512)


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

    data = jws.sign(payload, key=jwt_encode_key, headers=None, algorithm='RS256')

    response = StreamingResponse(iter([data]), media_type="text/plain")
    filename = f'client_configuration_token_{datetime.now().strftime("%d-%m-%y-%H-%M-%S")}'
    response.headers["Content-Disposition"] = f'attachment; filename={filename}'
    return response


# venv/lib/python3.9/site-packages/nls_services_auth/test/test_origins_controller.py
# {"candidate_origin_ref":"00112233-4455-6677-8899-aabbccddeeff","environment":{"fingerprint":{"mac_address_list":["ff:ff:ff:ff:ff:ff"]},"hostname":"my-hostname","ip_address_list":["192.168.178.123","fe80::","fe80::1%enp6s18"],"guest_driver_version":"510.85.02","os_platform":"Debian GNU/Linux 11 (bullseye) 11","os_version":"11 (bullseye)"},"registration_pending":false,"update_pending":false}
@app.post('/auth/v1/origin')
async def auth_origin(request: Request):
    j = json.loads((await request.body()).decode('utf-8'))

    candidate_origin_ref = j['candidate_origin_ref']
    print(f'> [  origin  ]: {candidate_origin_ref}: {j}')

    data = dict(
        candidate_origin_ref=candidate_origin_ref,
        hostname=j['environment']['hostname'],
        guest_driver_version=j['environment']['guest_driver_version'],
        os_platform=j['environment']['os_platform'], os_version=j['environment']['os_version']
    )
    db['origin'].insert_ignore(data, ['candidate_origin_ref'])

    cur_time = datetime.utcnow()
    response = {
        "origin_ref": candidate_origin_ref,
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
# {"code_challenge":"...","origin_ref":"00112233-4455-6677-8899-aabbccddeeff"}
@app.post('/auth/v1/code')
async def auth_code(request: Request):
    j = json.loads((await request.body()).decode('utf-8'))

    origin_ref = j['origin_ref']
    print(f'> [   code   ]: {origin_ref}: {j}')

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

    auth_code = jws.sign(payload, key=jwt_encode_key, headers={'kid': payload.get('kid')}, algorithm='RS256')

    response = {
        "auth_code": auth_code,
        "sync_timestamp": cur_time.isoformat(),
        "prompts": None
    }
    return JSONResponse(response)


# venv/lib/python3.9/site-packages/nls_services_auth/test/test_auth_controller.py
# venv/lib/python3.9/site-packages/nls_core_auth/auth.py - TokenResponse
# {"auth_code":"...","code_verifier":"..."}
@app.post('/auth/v1/token')
async def auth_token(request: Request):
    j = json.loads((await request.body()).decode('utf-8'))
    payload = jwt.decode(token=j['auth_code'], key=jwt_decode_key)

    origin_ref = payload['origin_ref']
    print(f'> [   auth   ]: {origin_ref}: {j}')

    # validate the code challenge
    if payload['challenge'] != b64enc(sha256(j['code_verifier'].encode('utf-8')).digest()).rstrip(b'=').decode('utf-8'):
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

    auth_token = jwt.encode(new_payload, key=jwt_encode_key, headers={'kid': payload.get('kid')}, algorithm='RS256')

    response = {
        "expires": access_expires_on.isoformat(),
        "auth_token": auth_token,
        "sync_timestamp": cur_time.isoformat(),
    }

    return JSONResponse(response)


# {'fulfillment_context': {'fulfillment_class_ref_list': []}, 'lease_proposal_list': [{'license_type_qualifiers': {'count': 1}, 'product': {'name': 'NVIDIA RTX Virtual Workstation'}}], 'proposal_evaluation_mode': 'ALL_OF', 'scope_ref_list': ['00112233-4455-6677-8899-aabbccddeeff']}
@app.post('/leasing/v1/lessor')
async def leasing_lessor(request: Request):
    j = json.loads((await request.body()).decode('utf-8'))
    token = jwt.decode(request.headers['authorization'].split(' ')[1], key=jwt_decode_key, algorithms='RS256', options={'verify_aud': False})

    code_challenge = token['origin_ref']
    scope_ref_list = j['scope_ref_list']
    print(f'> [  lessor  ]: {code_challenge}: {j}')
    print(f'> {code_challenge}: create leases for scope_ref_list {scope_ref_list}')

    cur_time = datetime.utcnow()
    lease_result_list = []
    for scope_ref in scope_ref_list:
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
        data = dict(origin_ref=code_challenge, lease_ref=scope_ref, expires=None, last_update=None)
        db['leases'].insert_ignore(data, ['origin_ref', 'lease_ref'])

    response = {
        "lease_result_list": lease_result_list,
        "result_code": "SUCCESS",
        "sync_timestamp": cur_time.isoformat(),
        "prompts": None
    }

    return JSONResponse(response)


# venv/lib/python3.9/site-packages/nls_services_lease/test/test_lease_multi_controller.py
@app.get('/leasing/v1/lessor/leases')
async def leasing_lessor_lease(request: Request):
    token = jwt.decode(request.headers['authorization'].split(' ')[1], key=key, algorithms='RS256', options={'verify_aud': False})

    code_challenge = token['origin_ref']
    active_lease_list = list(map(lambda x: x['lease_ref'], db['leases'].find(origin_ref=code_challenge)))
    print(f'> {code_challenge}: found {len(active_lease_list)} active leases')

    if len(active_lease_list) == 0:
        raise HTTPException(status_code=400, detail="No leases available")

    cur_time = datetime.utcnow()
    # venv/lib/python3.9/site-packages/nls_dal_service_instance_dls/schema/service_instance/V1_0_21__product_mapping.sql
    response = {
        # "active_lease_list": [
        #    # "BE276D7B-2CDB-11EC-9838-061A22468B59"  # (works on Linux) GRID-Virtual-WS 2.0 CONCURRENT_COUNTED_SINGLE // 'NVIDIA Virtual PC','NVIDIA Virtual PC'
        #    "BE276EFE-2CDB-11EC-9838-061A22468B59"  # GRID-Virtual-WS 2.0 CONCURRENT_COUNTED_SINGLE // 'NVIDIA RTX Virtual Workstation','NVIDIA RTX Virtual Workstation
        # ],
        "active_lease_list": active_lease_list,
        "sync_timestamp": cur_time.isoformat(),
        "prompts": None
    }

    return JSONResponse(response)


# venv/lib/python3.9/site-packages/nls_core_lease/lease_single.py
@app.put('/leasing/v1/lease/{lease_ref}')
async def leasing_lease_renew(request: Request, lease_ref: str):
    token = jwt.decode(request.headers['authorization'].split(' ')[1], key=jwt_decode_key, algorithms='RS256', options={'verify_aud': False})

    code_challenge = token['origin_ref']
    print(f'> {code_challenge}: renew {lease_ref}')

    if db['leases'].count(lease_ref=lease_ref) == 0:
        raise HTTPException(status_code=400, detail="No leases available")

    cur_time = datetime.utcnow()
    expires = cur_time + LEASE_EXPIRE_DELTA
    response = {
        "lease_ref": lease_ref,
        "expires": expires.isoformat(),
        "recommended_lease_renewal": 0.16,
        # 0.16 = 10 min, 0.25 = 15 min, 0.33 = 20 min, 0.5 = 30 min (should be lower than "LEASE_EXPIRE_DELTA")
        "offline_lease": True,
        "prompts": None,
        "sync_timestamp": cur_time.isoformat(),
    }

    data = dict(lease_ref=lease_ref, origin_ref=code_challenge, expires=expires, last_update=cur_time)
    db['leases'].update(data, ['lease_ref'])

    return JSONResponse(response)


@app.delete('/leasing/v1/lessor/leases')
async def leasing_lessor_lease_remove(request: Request):
    token = jwt.decode(request.headers['authorization'].split(' ')[1], key=jwt_decode_key, algorithms='RS256', options={'verify_aud': False})

    code_challenge = token['origin_ref']
    released_lease_list = list(map(lambda x: x['lease_ref'], db['leases'].find(origin_ref=code_challenge)))
    deletions = db['leases'].delete(origin_ref=code_challenge)
    print(f'> {code_challenge}: removed {deletions} leases')

    cur_time = datetime.utcnow()
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

    print(f'> Starting dev-server ...')

    ssl_keyfile = join(dirname(__file__), 'cert/webserver.key')
    ssl_certfile = join(dirname(__file__), 'cert/webserver.crt')

    uvicorn.run('main:app', host='0.0.0.0', port=443, ssl_keyfile=ssl_keyfile, ssl_certfile=ssl_certfile, reload=True)
