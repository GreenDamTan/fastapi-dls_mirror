import json
import sys
from base64 import b64encode as b64enc
from calendar import timegm
from datetime import datetime, UTC
from hashlib import sha256
from uuid import uuid4, UUID

from dateutil.relativedelta import relativedelta
from jose import jwt, jwk, jws
from jose.constants import ALGORITHMS
from starlette.testclient import TestClient

# add relative path to use packages as they were in the app/ dir
sys.path.append('../')
sys.path.append('../app')

from app import main
from util import CASetup, PrivateKey, PublicKey, Cert

client = TestClient(main.app)

# Instance
INSTANCE_REF = '10000000-0000-0000-0000-000000000001'
ORIGIN_REF, ALLOTMENT_REF, SECRET = str(uuid4()), '20000000-0000-0000-0000-000000000001', 'HelloWorld'

# CA & Signing
ca_setup = CASetup(service_instance_ref=INSTANCE_REF)
my_root_certificate = Cert.from_file(ca_setup.root_certificate_filename)
my_si_private_key = PrivateKey.from_file(ca_setup.si_private_key_filename)
my_si_private_key_as_pem = my_si_private_key.pem()
my_si_public_key = my_si_private_key.public_key()
my_si_public_key_as_pem = my_si_private_key.public_key().pem()

jwt_encode_key = jwk.construct(my_si_private_key_as_pem, algorithm=ALGORITHMS.RS256)
jwt_decode_key = jwk.construct(my_si_public_key_as_pem, algorithm=ALGORITHMS.RS256)


def __bearer_token(origin_ref: str) -> str:
    token = jwt.encode({"origin_ref": origin_ref}, key=jwt_encode_key, algorithm=ALGORITHMS.RS256)
    token = f'Bearer {token}'
    return token


def test_signing():
    signature_set_header = my_si_private_key.generate_signature(b'Hello')

    # test plain
    my_si_public_key.verify_signature(signature_set_header, b'Hello')

    # test "X-NLS-Signature: b'....'
    x_nls_signature_header_value = f'{signature_set_header.hex().encode()}'
    assert f'{x_nls_signature_header_value}'.startswith('b\'')
    assert f'{x_nls_signature_header_value}'.endswith('\'')

    # test eval
    signature_get_header = eval(x_nls_signature_header_value)
    signature_get_header = bytes.fromhex(signature_get_header.decode('ascii'))
    my_si_public_key.verify_signature(signature_get_header, b'Hello')


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


def test_config_root_ca():
    response = client.get('/-/config/root-ca')
    assert response.status_code == 200
    assert response.content.decode('utf-8') == my_root_certificate.pem().decode('utf-8')


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
            'product': {'name': 'NVIDIA Virtual Applications'}
        }],
        'proposal_evaluation_mode': 'ALL_OF',
        'scope_ref_list': [ALLOTMENT_REF]
    }

    response = client.post('/leasing/v1/lessor', json=payload, headers={'authorization': __bearer_token(ORIGIN_REF)})
    assert response.status_code == 200

    client_challenge = response.json().get('client_challenge')
    assert client_challenge == payload.get('client_challenge')
    signature = eval(response.headers.get('X-NLS-Signature'))
    assert len(signature) == 512
    signature = bytes.fromhex(signature.decode('ascii'))
    assert len(signature) == 256
    my_si_public_key.verify_signature(signature, response.content)

    lease_result_list = response.json().get('lease_result_list')
    assert len(lease_result_list) == 1
    assert len(lease_result_list[0]['lease']['ref']) == 36
    assert str(UUID(lease_result_list[0]['lease']['ref'])) == lease_result_list[0]['lease']['ref']
    assert lease_result_list[0]['lease']['product_name'] == 'NVIDIA Virtual Applications'
    assert lease_result_list[0]['lease']['feature_name'] == 'GRID-Virtual-Apps'



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
    signature = eval(response.headers.get('X-NLS-Signature'))
    assert len(signature) == 512
    signature = bytes.fromhex(signature.decode('ascii'))
    assert len(signature) == 256
    my_si_public_key.verify_signature(signature, response.content)

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
            'product': {'name': 'NVIDIA Virtual Applications'}
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
