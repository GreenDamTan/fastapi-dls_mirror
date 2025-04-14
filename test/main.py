import json
import sys
from base64 import b64encode as b64enc
from calendar import timegm
from datetime import datetime, UTC
from hashlib import sha256
from os.path import dirname, join
from uuid import uuid4, UUID

from dateutil.relativedelta import relativedelta
from jose import jwt, jwk, jws
from jose.constants import ALGORITHMS
from starlette.testclient import TestClient

# add relative path to use packages as they were in the app/ dir
sys.path.append('../')
sys.path.append('../app')

from app import main
from util import PrivateKey, PublicKey

client = TestClient(main.app)

INSTANCE_REF = '10000000-0000-0000-0000-000000000001'
ORIGIN_REF, ALLOTMENT_REF, SECRET = str(uuid4()), '20000000-0000-0000-0000-000000000001', 'HelloWorld'

# INSTANCE_KEY_RSA = generate_key()
# INSTANCE_KEY_PUB = INSTANCE_KEY_RSA.public_key()

INSTANCE_KEY_RSA = PrivateKey.from_file(str(join(dirname(__file__), '../app/cert/instance.private.pem')))
INSTANCE_KEY_PUB = PublicKey.from_file(str(join(dirname(__file__), '../app/cert/instance.public.pem')))

jwt_encode_key = jwk.construct(INSTANCE_KEY_RSA.pem(), algorithm=ALGORITHMS.RS256)
jwt_decode_key = jwk.construct(INSTANCE_KEY_PUB.pem(), algorithm=ALGORITHMS.RS256)


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
    assert response.json().get('status') == 'up'


def test_config():
    response = client.get('/-/config')
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


def test_config_token():  # todo: /leasing/v1/config-token
    # https://git.collinwebdesigns.de/nvidia/nls/-/blob/main/src/test/test_config_token.py

    response = client.post('/leasing/v1/config-token', json={"service_instance_ref": INSTANCE_REF})
    assert response.status_code == 200

    nv_response_certificate_configuration = response.json().get('certificateConfiguration')
    nv_response_public_cert = nv_response_certificate_configuration.get('publicCert').encode('utf-8')
    nv_jwt_decode_key = jwk.construct(nv_response_public_cert, algorithm=ALGORITHMS.RS256)

    nv_response_config_token = response.json().get('configToken')

    payload = jws.verify(nv_response_config_token, key=nv_jwt_decode_key, algorithms=ALGORITHMS.RS256)
    payload = json.loads(payload)
    assert payload.get('iss') == 'NLS Service Instance'
    assert payload.get('aud') == 'NLS Licensed Client'
    assert payload.get('service_instance_ref') == INSTANCE_REF

    nv_si_public_key_configuration = payload.get('service_instance_public_key_configuration')
    nv_si_public_key_me = nv_si_public_key_configuration.get('service_instance_public_key_me')
    # assert nv_si_public_key_me.get('mod') == 1  #nv_si_public_key_mod
    assert len(nv_si_public_key_me.get('mod')) == 512
    assert nv_si_public_key_me.get('exp') == 65537  # nv_si_public_key_exp


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
    assert response.json().get('origin_ref') == ORIGIN_REF



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
    assert response.json().get('origin_ref') == ORIGIN_REF


def test_auth_v1_code():
    payload = {
        "code_challenge": b64enc(sha256(SECRET.encode('utf-8')).digest()).rstrip(b'=').decode('utf-8'),
        "origin_ref": ORIGIN_REF,
    }

    response = client.post('/auth/v1/code', json=payload)
    assert response.status_code == 200

    payload = jwt.get_unverified_claims(token=response.json().get('auth_code'))
    assert payload.get('origin_ref') == ORIGIN_REF


def test_auth_v1_token():
    cur_time = datetime.now(UTC)
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
        "auth_code": jwt.encode(payload, key=jwt_encode_key, headers={'kid': payload.get('kid')}, algorithm=ALGORITHMS.RS256),
        "code_verifier": SECRET,
    }

    response = client.post('/auth/v1/token', json=payload)
    assert response.status_code == 200

    token = response.json().get('auth_token')
    payload = jwt.decode(token=token, key=jwt_decode_key, algorithms=ALGORITHMS.RS256, options={'verify_aud': False})
    assert payload.get('origin_ref') == ORIGIN_REF


def test_leasing_v1_lessor():
    payload = {
        'client_challenge': 'my_unique_string',
        'fulfillment_context': {
            'fulfillment_class_ref_list': []
        },
        'lease_proposal_list': [{
            'license_type_qualifiers': {'count': 1},
            'product': {'name': 'NVIDIA RTX Virtual Workstation'}
        }],
        'proposal_evaluation_mode': 'ALL_OF',
        'scope_ref_list': [ALLOTMENT_REF]
    }

    response = client.post('/leasing/v1/lessor', json=payload, headers={'authorization': __bearer_token(ORIGIN_REF)})
    assert response.status_code == 200

    client_challenge = response.json().get('client_challenge')
    assert client_challenge == payload.get('client_challenge')

    lease_result_list = response.json().get('lease_result_list')
    assert len(lease_result_list) == 1
    assert len(lease_result_list[0]['lease']['ref']) == 36
    assert str(UUID(lease_result_list[0]['lease']['ref'])) == lease_result_list[0]['lease']['ref']


def test_leasing_v1_lessor_lease():
    response = client.get('/leasing/v1/lessor/leases', headers={'authorization': __bearer_token(ORIGIN_REF)})
    assert response.status_code == 200

    active_lease_list = response.json().get('active_lease_list')
    assert len(active_lease_list) == 1
    assert len(active_lease_list[0]) == 36
    assert str(UUID(active_lease_list[0])) == active_lease_list[0]


def test_leasing_v1_lease_renew():
    response = client.get('/leasing/v1/lessor/leases', headers={'authorization': __bearer_token(ORIGIN_REF)})
    active_lease_list = response.json().get('active_lease_list')
    active_lease_ref = active_lease_list[0]

    ###

    payload = {'client_challenge': 'my_unique_string'}
    response = client.put(f'/leasing/v1/lease/{active_lease_ref}', json=payload, headers={'authorization': __bearer_token(ORIGIN_REF)})
    assert response.status_code == 200

    client_challenge = response.json().get('client_challenge')
    assert client_challenge == payload.get('client_challenge')

    lease_ref = response.json().get('lease_ref')
    assert len(lease_ref) == 36
    assert lease_ref == active_lease_ref


def test_leasing_v1_lease_delete():
    response = client.get('/leasing/v1/lessor/leases', headers={'authorization': __bearer_token(ORIGIN_REF)})
    active_lease_list = response.json().get('active_lease_list')
    active_lease_ref = active_lease_list[0]

    ###

    response = client.delete(f'/leasing/v1/lease/{active_lease_ref}', headers={'authorization': __bearer_token(ORIGIN_REF)})
    assert response.status_code == 200

    lease_ref = response.json().get('lease_ref')
    assert len(lease_ref) == 36
    assert lease_ref == active_lease_ref


def test_leasing_v1_lessor_lease_remove():
    # see "test_leasing_v1_lessor()"
    payload = {
        'fulfillment_context': {
            'fulfillment_class_ref_list': []
        },
        'lease_proposal_list': [{
            'license_type_qualifiers': {'count': 1},
            'product': {'name': 'NVIDIA RTX Virtual Workstation'}
        }],
        'proposal_evaluation_mode': 'ALL_OF',
        'scope_ref_list': [ALLOTMENT_REF]
    }

    response = client.post('/leasing/v1/lessor', json=payload, headers={'authorization': __bearer_token(ORIGIN_REF)})
    lease_result_list = response.json().get('lease_result_list')
    lease_ref = lease_result_list[0]['lease']['ref']
    #

    response = client.delete('/leasing/v1/lessor/leases', headers={'authorization': __bearer_token(ORIGIN_REF)})
    assert response.status_code == 200

    released_lease_list = response.json().get('released_lease_list')
    assert len(released_lease_list) == 1
    assert len(released_lease_list[0]) == 36
    assert released_lease_list[0] == lease_ref
