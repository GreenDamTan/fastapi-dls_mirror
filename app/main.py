from base64 import b64encode
from hashlib import sha256
from uuid import uuid4

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

URL = '192.168.178.196'
SITE_KEY_FILE = load_key('/opt/fastapi-dls/site.key')
SITE_KEY_XID = '00000000-0000-0000-0000-000000000000'

SITE_KEY_RSA = private_bytes(SITE_KEY_FILE)
SITE_KEY_PUB = public_key(SITE_KEY_FILE)


@app.get('/')
async def index():
    return {'hello': 'world'}


@app.get('/status')
async def status(request: Request):
    return JSONResponse({'status': 'up'})


# venv/lib/python3.9/site-packages/nls_core_service_instance/service_instance_token_manager.py
@app.get('/client-token')
async def client_token():
    public_key_me = SITE_KEY_FILE.public_key().public_numbers()
    service_instance_public_key_me = {
        "mod": hex(public_key_me.n)[2:],
        "exp": public_key_me.e,
    },

    cur_time = datetime.utcnow()
    exp_time = cur_time + relativedelta(years=12)
    payload = {
        "jti": str(uuid4()),
        "iss": "NLS Service Instance",
        "aud": "NLS Licensed Client",
        "iat": cur_time,
        "nbf": cur_time,
        "exp": exp_time,
        "update_mode": "ABSOLUTE",
        "scope_ref_list": [
            "482f24b5-0a60-4ec2-a63a-9ed00bc2534e"
            # todo: "scope_ref_list" should be a unique client id (which identifies leases, etc.)
        ],
        "fulfillment_class_ref_list": [],
        "service_instance_configuration": {
            "nls_service_instance_ref": "b43d6e46-d6d0-4943-8b8d-c66a5f6e0d38",
            "svc_port_set_list": [
                {
                    "idx": 0,
                    "d_name": "DLS",
                    "svc_port_map": [
                        {"service": "auth", "port": 443},
                        {"service": "lease", "port": 443}
                    ]
                }
            ],
            "node_url_list": [{"idx": 0, "url": URL, "url_qr": URL, "svc_port_set_idx": 0}]
        },
        "service_instance_public_key_configuration": {
            "service_instance_public_key_me": service_instance_public_key_me,
            "service_instance_public_key_pem": SITE_KEY_PUB.decode('utf-8'),
            "key_retention_mode": "LATEST_ONLY"
        }
    }

    key = jwk.construct(SITE_KEY_RSA, algorithm=ALGORITHMS.RS512)
    data = jwt.encode(payload, key=key, headers=None, algorithm='RS256')

    response = StreamingResponse(iter([data]), media_type="text/plain")
    response.headers["Content-Disposition"] = "attachment; filename=client_token.tok"
    return response


# venv/lib/python3.9/site-packages/nls_services_auth/test/test_origins_controller.py
@app.post('/auth/v1/origin')
async def auth(request: Request, status_code=201):
    body = await request.body()
    body = body.decode('utf-8')
    j = json.loads(body)
    # {"candidate_origin_ref":"00112233-4455-6677-8899-aabbccddeeff","environment":{"fingerprint":{"mac_address_list":["fa:52:16:65:c5:28"]},"hostname":"debian-grid-test","ip_address_list":["192.168.178.12","fdfe:7fcd:e30f:40f5:f852:16ff:fe65:c528","fe80::f852:16ff:fe65:c528%enp6s18"],"guest_driver_version":"510.85.02","os_platform":"Debian GNU/Linux 11 (bullseye) 11","os_version":"11 (bullseye)"},"registration_pending":false,"update_pending":false}

    cur_time = datetime.utcnow()
    response = {
        "origin_ref": j['candidate_origin_ref'],
        "environment": {
            "fingerprint": {"mac_address_list": ["e4:b9:7a:e5:7b:ff"]},
            "guest_driver_version": "guest_driver_version",
            "hostname": "myhost",
            "os_platform": "os_platform",
            "os_version": "os_version",
            "ip_address_list": ["192.168.1.129"]
        },
        "svc_port_set_list": None,
        "node_url_list": None,
        "node_query_order": None,
        "prompts": None,
        "sync_timestamp": cur_time
    }
    return response


# venv/lib/python3.9/site-packages/nls_services_auth/test/test_auth_controller.py
# venv/lib/python3.9/site-packages/nls_core_auth/auth.py - CodeResponse
@app.post('/auth/v1/code')
async def code(request: Request):
    body = await request.body()
    body = body.decode('utf-8')
    j = json.loads(body)
    # {"code_challenge":"QhDaArKDQwFeQ5Jq4Dn5hy37ODF8Jq3igXCXvWEgs5I","origin_ref":"00112233-4455-6677-8899-aabbccddeeff"}

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
    key = jwk.construct(SITE_KEY_RSA, algorithm=ALGORITHMS.RS512)
    auth_code = jws.sign(payload, key, headers=headers, algorithm='RS256')

    response = {
        "auth_code": auth_code,
        "sync_timestamp": datetime.utcnow(),
        "prompts": None
    }
    return response


# venv/lib/python3.9/site-packages/nls_services_auth/test/test_auth_controller.py
# venv/lib/python3.9/site-packages/nls_core_auth/auth.py - TokenResponse
@app.post('/auth/v1/token')
async def token(request: Request):
    body = await request.body()
    body = body.decode('utf-8')
    j = json.loads(body)
    # {"auth_code":"eyJhbGciOiJSUzI1NiIsImtpZCI6IjAwMDAwMDAwLTAwMDAtMDAwMC0wMDAwLTAwMDAwMDAwMDAwMCIsInR5cCI6IkpXVCJ9.eyJpYXQiOjE2NzExODI5MTQsImV4cCI6MTY3MTI2OTMxNCwiY2hhbGxlbmdlIjoiaXdZdFpIME03K0ZZUWdRQXEwbjhabThWcFpJbWdtV1NDSXI1MkdTSlMxayIsIm9yaWdpbl9yZWYiOiJpd1l0WkgwTTcrRllRZ1FBcTBuOFptOFZwWkltZ21XU0NJcjUyR1NKUzFrIiwia2V5X3JlZiI6IjAwMDAwMDAwLTAwMDAtMDAwMC0wMDAwLTAwMDAwMDAwMDAwMCIsImtpZCI6IjAwMDAwMDAwLTAwMDAtMDAwMC0wMDAwLTAwMDAwMDAwMDAwMCJ9.hkBPQx7UbXqwRzpTSp5fASwLg7rJOgjDOGD98Zh6pEkPW09KjxcsaHKeR8KIZmDS1S_kLed93-UzUY4wXAylFBlM-daL-TEbHJau2muZGWXPrtdsGLI9CLFcc0dmocq1_5rnRV3liqjdZwL8djK9Fx_5tOzEfeI9oCJ49Sh2LD_p1vkFcqUv9z9mVL9IGsoRM6y4hJ2YKBloijzhMLp5E7nojyD6Z8PQZ0mOIOc3tncAaXQS47JhgGsJPUDR-YoLF5uNpAlJKZP2eZWJt3P7MvhIz3lxFPUJ5jHX64Vf0Ds10-GBctZuy1-eCLBXj74uQy_U4KlnCif-5N8bPTvgxw","code_verifier":"CgnDPaugQCb4U6l3EfJSFsA/JxMqNO4TqONeb9yl8EVRWU88yTPlEeJgZQO0f/JVnScYOsvwa0jcvTAMBulEKgucfxDDVL1cBOylGugQ0QlJsXU5hJ8VLAQtOyPthnVyEutERNyOKVwl3YI5Z5EfUcfuhDqmxBUpnAFtQ9H3R3g"}

    # payload = self._security.get_valid_payload(req.auth_code)  # todo
    key = jwk.construct(SITE_KEY_PUB, algorithm=ALGORITHMS.RS512)
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
    key = jwk.construct(SITE_KEY_RSA, algorithm=ALGORITHMS.RS512)
    auth_token = jwt.encode(new_payload, key=key, headers=headers, algorithm='RS256')

    response = {
        "expires": access_expires_on,
        "auth_token": auth_token,
        "sync_timestamp": cur_time,
    }

    return response


@app.post('/leasing/v1/lessor')
async def lessor(request: Request):
    body = await request.body()
    body = body.decode('utf-8')
    j = json.loads(body)
    # {'fulfillment_context': {'fulfillment_class_ref_list': []}, 'lease_proposal_list': [{'license_type_qualifiers': {'count': 1}, 'product': {'name': 'NVIDIA RTX Virtual Workstation'}}], 'proposal_evaluation_mode': 'ALL_OF', 'scope_ref_list': ['482f24b5-0a60-4ec2-a63a-9ed00bc2534e']}

    cur_time = datetime.utcnow()
    # todo: keep track of leases, to return correct list on '/leasing/v1/lessor/leases'
    lease_result_list = []
    for scope_ref in j['scope_ref_list']:
        lease_result_list.append({
            "ordinal": 0,
            "lease": {
                "ref": scope_ref,
                "created": cur_time,
                "expires": cur_time + relativedelta(minutes=15),  # days=90
                "recommended_lease_renewal": 0.15,
                "offline_lease": "true",
                "license_type": "CONCURRENT_COUNTED_SINGLE"
            }
        })

    response = {
        "lease_result_list": lease_result_list,
        "result_code": "SUCCESS",
        "sync_timestamp": cur_time,
        "prompts": None
    }

    return response


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
        "sync_timestamp": cur_time,
        "prompts": None
    }

    return response


@app.delete('/leasing/v1/lessor/leases')
async def lease_remove(request: Request, status_code=200):
    cur_time = datetime.utcnow()
    response = {
        "released_lease_list": None,
        "release_failure_list": None,
        "sync_timestamp": cur_time,
        "prompts": None
    }
    return response


if __name__ == '__main__':
    import uvicorn

    ssl_keyfile = 'key.pem'
    ssl_certfile = 'cert.pem'

    uvicorn.run('main:app', host='0.0.0.0', port=443, ssl_keyfile=ssl_keyfile, ssl_certfile=ssl_certfile)
