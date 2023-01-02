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

# add relative path to use packages as they were in the app/ dir
sys.path.append('../')
sys.path.append('../app')

from app import main
from app.util import load_key

client = TestClient(main.app)

ORIGIN_REF, LEASE_REF = str(uuid4()), str(uuid4())
SECRET = "HelloWorld"

# INSTANCE_KEY_RSA = generate_key()
# INSTANCE_KEY_PUB = INSTANCE_KEY_RSA.public_key()

INSTANCE_KEY_RSA = load_key(str(join(dirname(__file__), '../app/cert/instance.private.pem')))
INSTANCE_KEY_PUB = load_key(str(join(dirname(__file__), '../app/cert/instance.public.pem')))

jwt_encode_key = jwk.construct(INSTANCE_KEY_RSA.export_key().decode('utf-8'), algorithm=ALGORITHMS.RS256)
jwt_decode_key = jwk.construct(INSTANCE_KEY_PUB.export_key().decode('utf-8'), algorithm=ALGORITHMS.RS256)


def __bearer_token(origin_ref: str) -> str:
    token = jwt.encode({"origin_ref": origin_ref}, key=jwt_encode_key, algorithm=ALGORITHMS.RS256)
    token = f'Bearer {token}'
    return token


def test_index():
    response = client.get('/')
    assert response.status_code == 200



def test_health():
    response = client.get('/-/health')
    assert response.status_code == 200
    assert response.json()['status'] == 'up'


def test_config():
    response = client.get('/-/')
    assert response.status_code == 200


def test_readme():
    response = client.get('/-/readme')
    assert response.status_code == 200


def test_manage():
    response = client.get('/-/manage')
    assert response.status_code == 200


def test_client_token():
    response = client.get('/-/client-token')
    assert response.status_code == 200


def test_origins():
    pass


def test_origins_delete():
    pass


def test_leases():
    pass


def test_lease_delete():
    pass


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


def auth_v1_origin_update():
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

    response = client.post('/auth/v1/origin/update', json=payload)
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
    payload = {
        'fulfillment_context': {
            'fulfillment_class_ref_list': []
        },
        'lease_proposal_list': [{
            'license_type_qualifiers': {'count': 1},
            'product': {'name': 'NVIDIA RTX Virtual Workstation'}
        }],
        'proposal_evaluation_mode': 'ALL_OF',
        'scope_ref_list': [LEASE_REF]
    }

    response = client.post('/leasing/v1/lessor', json=payload, headers={'authorization': __bearer_token(ORIGIN_REF)})
    assert response.status_code == 200

    lease_result_list = response.json()['lease_result_list']
    assert len(lease_result_list) == 1
    assert lease_result_list[0]['lease']['ref'] == LEASE_REF


def test_leasing_v1_lessor_lease():
    response = client.get('/leasing/v1/lessor/leases', headers={'authorization': __bearer_token(ORIGIN_REF)})
    assert response.status_code == 200

    active_lease_list = response.json()['active_lease_list']
    assert len(active_lease_list) == 1
    assert active_lease_list[0] == LEASE_REF


def test_leasing_v1_lease_renew():
    response = client.put(f'/leasing/v1/lease/{LEASE_REF}', headers={'authorization': __bearer_token(ORIGIN_REF)})
    assert response.status_code == 200

    assert response.json()['lease_ref'] == LEASE_REF


def test_leasing_v1_lease_delete():
    response = client.delete(f'/leasing/v1/lease/{LEASE_REF}', headers={'authorization': __bearer_token(ORIGIN_REF)})
    assert response.status_code == 200

    assert response.json()['lease_ref'] == LEASE_REF


def test_leasing_v1_lessor_lease_remove():
    test_leasing_v1_lessor()

    response = client.delete('/leasing/v1/lessor/leases', headers={'authorization': __bearer_token(ORIGIN_REF)})
    assert response.status_code == 200

    released_lease_list = response.json()['released_lease_list']
    assert len(released_lease_list) == 1
    assert released_lease_list[0] == LEASE_REF
