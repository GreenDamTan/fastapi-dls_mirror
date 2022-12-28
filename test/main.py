from base64 import b64encode as b64enc
from hashlib import sha256
from calendar import timegm
from datetime import datetime
from os.path import dirname, join
from uuid import uuid4

from dateutil.relativedelta import relativedelta
from jose import jwt, jwk
from jose.constants import ALGORITHMS
from starlette.testclient import TestClient
import sys

from app.util import generate_key, load_key

# add relative path to use packages as they were in the app/ dir
sys.path.append('../')
sys.path.append('../app')

from app import main

client = TestClient(main.app)

ORIGIN_REF = str(uuid4())
SECRET = "HelloWorld"

# INSTANCE_KEY_RSA = generate_key()
# INSTANCE_KEY_PUB = INSTANCE_KEY_RSA.public_key()

INSTANCE_KEY_RSA = load_key(str(join(dirname(__file__), '../app/cert/instance.private.pem')))
INSTANCE_KEY_PUB = load_key(str(join(dirname(__file__), '../app/cert/instance.public.pem')))

jwt_encode_key = jwk.construct(INSTANCE_KEY_RSA.export_key().decode('utf-8'), algorithm=ALGORITHMS.RS256)
jwt_decode_key = jwk.construct(INSTANCE_KEY_PUB.export_key().decode('utf-8'), algorithm=ALGORITHMS.RS256)


def test_index():
    response = client.get('/')
    assert response.status_code == 200


def test_status():
    response = client.get('/status')
    assert response.status_code == 200
    assert response.json()['status'] == 'up'


def test_client_token():
    response = client.get('/client-token')
    assert response.status_code == 200


def test_auth_v1_origin():
    payload = {
        "registration_pending": False,
        "environment": {
            "guest_driver_version": "guest_driver_version",
            "hostname": "myhost",
            "ip_address_list": ["192.168.1.123"],
            "os_version": "os_version",
            "os_platform": "os_platform",
            "fingerprint": {"mac_address_list": ["ff:ff:ff:ff:ff:ff"]},
            "host_driver_version": "host_driver_version"
        },
        "update_pending": False,
        "candidate_origin_ref": ORIGIN_REF,
    }

    response = client.post('/auth/v1/origin', json=payload)
    assert response.status_code == 200
    assert response.json()['origin_ref'] == ORIGIN_REF


def test_auth_v1_code():
    payload = {
        "code_challenge": b64enc(sha256(SECRET.encode('utf-8')).digest()).rstrip(b'=').decode('utf-8'),
        "origin_ref": ORIGIN_REF,
    }

    response = client.post('/auth/v1/code', json=payload)
    assert response.status_code == 200

    payload = jwt.get_unverified_claims(token=response.json()['auth_code'])
    assert payload['origin_ref'] == ORIGIN_REF


def test_auth_v1_token():
    cur_time = datetime.utcnow()
    access_expires_on = cur_time + relativedelta(hours=1)

    payload = {
        "iat": timegm(cur_time.timetuple()),
        "exp": timegm(access_expires_on.timetuple()),
        "challenge": b64enc(sha256(SECRET.encode('utf-8')).digest()).rstrip(b'=').decode('utf-8'),
        "origin_ref": ORIGIN_REF,
        "key_ref": "00000000-0000-0000-0000-000000000000",
        "kid": "00000000-0000-0000-0000-000000000000"
    }
    payload = {
        "auth_code": jwt.encode(payload, key=jwt_encode_key, headers={'kid': payload.get('kid')},
                                algorithm=ALGORITHMS.RS256),
        "code_verifier": SECRET,
    }

    response = client.post('/auth/v1/token', json=payload)
    assert response.status_code == 200

    token = response.json()['auth_token']
    payload = jwt.decode(token=token, key=jwt_decode_key, algorithms=ALGORITHMS.RS256, options={'verify_aud': False})
    assert payload['origin_ref'] == ORIGIN_REF


def test_leasing_v1_lessor():
    pass


def test_leasing_v1_lessor_lease():
    pass


def test_leasing_v1_lease_renew():
    pass


def test_leasing_v1_lessor_lease_remove():
    pass
