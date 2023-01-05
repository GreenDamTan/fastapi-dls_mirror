# Reverse Engineering Notes

# Usefully commands

## Check licensing status

- `nvidia-smi -q | grep "License"`

**Output**

```
vGPU Software Licensed Product
        License Status                    : Licensed (Expiry: 2023-1-14 12:59:52 GMT)
```

## Track licensing progress

- NVIDIA Grid Log: `journalctl -u nvidia-gridd -f`

```
systemd[1]: Started NVIDIA Grid Daemon.
nvidia-gridd[2986]: Configuration parameter ( ServerAddress  ) not set
nvidia-gridd[2986]: vGPU Software package (0)
nvidia-gridd[2986]: Ignore service provider and node-locked licensing
nvidia-gridd[2986]: NLS initialized
nvidia-gridd[2986]: Acquiring license. (Info: license.nvidia.space; NVIDIA RTX Virtual Workstation)
nvidia-gridd[2986]: License acquired successfully. (Info: license.nvidia.space, NVIDIA RTX Virtual Workstation; Expiry: 2023-1-29 22:3:0 GMT)
```

# DLS-Container File-System (Docker)

## Configuration data

Most variables and configs are stored in `/var/lib/docker/volumes/configurations/_data`.

Files can be modified with `docker cp <container-id>:/venv/... /opt/localfile/...` and back.
(May you need to fix permissions with `docker exec -u 0 <container-id> chown nonroot:nonroot /venv/...`)

## Dive / Docker image inspector

- `dive dls:appliance`

The source code is stored in `/venv/lib/python3.9/site-packages/nls_*`.

Image-Reference:

```
Tags:   (unavailable)
Id:     d1c7976a5d2b3681ff6c5a30f8187e4015187a83f3f285ba4a37a45458bd6b98
Digest: sha256:311223c5af7a298ec1104f5dc8c3019bfb0e1f77256dc3d995244ffb295a97
1f
Command:
#(nop) ADD file:c1900d3e3a29c29a743a8da86c437006ec5d2aa873fb24e48033b6bf492bb37b in /
```

## Private Key (Site-Key)

- `/etc/dls/config/decryptor/decryptor`

```shell
 docker exec -it <container-id> /etc/dls/config/decryptor/decryptor > /tmp/private-key.pem
```

```
-----BEGIN RSA PRIVATE KEY-----
...
-----END RSA PRIVATE KEY-----
``` 

## Site Key Uri - `/etc/dls/config/site_key_uri.bin`

```
base64-content...
```

## DB Password - `/etc/dls/config/dls_db_password.bin`

```
base64-content...
```

**Decrypt database password**

```
cd /var/lib/docker/volumes/configurations/_data
cat dls_db_password.bin | base64 -d > dls_db_password.bin.raw
openssl rsautl -decrypt -inkey /tmp/private-key.pem -in dls_db_password.bin.raw
```

# Database

- It's enough to manipulate database licenses. There must not be changed any line of code to bypass licensing
  validations.

# Logging / Stack Trace

- https://docs.nvidia.com/license-system/latest/nvidia-license-system-user-guide/index.html#troubleshooting-dls-instance

**Failed licensing log**

```
{
    "activity": 100,
    "context": {
        "SERVICE_INSTANCE_ID": "b43d6e46-d6d0-4943-8b8d-c66a5f6e0d38",
        "SERVICE_INSTANCE_NAME": "DEFAULT_2022-12-14_12:48:30",
        "description": "borrow failed: NotFoundError(no pool features found for: NVIDIA RTX Virtual Workstation)",
        "event_type": null,
        "function_name": "_evt",
        "lineno": 54,
        "module_name": "nls_dal_lease_dls.event",
        "operation_id": "e72a8ca7-34cc-4e11-b80c-273592085a24",
        "origin_ref": "3f7f5a50-a26b-425b-8d5e-157f63e72b1c",
        "service_name": "nls_services_lease"
    },
    "detail": {
        "oc": {
            "license_allotment_xid": "10c4317f-7c4c-11ed-a524-0e4252a7e5f1",
            "origin_ref": "3f7f5a50-a26b-425b-8d5e-157f63e72b1c",
            "service_instance_xid": "b43d6e46-d6d0-4943-8b8d-c66a5f6e0d38"
        },
        "operation_id": "e72a8ca7-34cc-4e11-b80c-273592085a24"
    },
    "id": "0cc9e092-3b92-4652-8d9e-7622ef85dc79",
    "metadata": {},
    "ts": "2022-12-15T10:25:36.827661Z"
}

{
    "activity": 400,
    "context": {
        "SERVICE_INSTANCE_ID": "b43d6e46-d6d0-4943-8b8d-c66a5f6e0d38",
        "SERVICE_INSTANCE_NAME": "DEFAULT_2022-12-14_12:48:30",
        "description": "lease_multi_create failed: no pool features found for: NVIDIA RTX Virtual Workstation",
        "event_by": "system",
        "function_name": "lease_multi_create",
        "level": "warning",
        "lineno": 157,
        "module_name": "nls_services_lease.controllers.lease_multi_controller",
        "operation_id": "e72a8ca7-34cc-4e11-b80c-273592085a24",
        "service_name": "nls_services_lease"
    },
    "detail": {
        "_msg": "lease_multi_create failed: no pool features found for: NVIDIA RTX Virtual Workstation",
        "exec_info": ["NotFoundError", "NotFoundError(no pool features found for: NVIDIA RTX Virtual Workstation)", "  File \"/venv/lib/python3.9/site-packages/nls_services_lease/controllers/lease_multi_controller.py\", line 127, in lease_multi_create\n    data = _leaseMulti.lease_multi_create(event_args)\n  File \"/venv/lib/python3.9/site-packages/nls_core_lease/lease_multi.py\", line 208, in lease_multi_create\n    raise e\n  File \"/venv/lib/python3.9/site-packages/nls_core_lease/lease_multi.py\", line 184, in lease_multi_create\n    self._try_proposals(oc, mlr, results, detail)\n  File \"/venv/lib/python3.9/site-packages/nls_core_lease/lease_multi.py\", line 219, in _try_proposals\n    lease = self._leases.create(creator)\n  File \"/venv/lib/python3.9/site-packages/nls_dal_lease_dls/leases.py\", line 230, in create\n    features = self._get_features(creator)\n  File \"/venv/lib/python3.9/site-packages/nls_dal_lease_dls/leases.py\", line 148, in _get_features\n    self._explain_not_available(cur, creator)\n  File \"/venv/lib/python3.9/site-packages/nls_dal_lease_dls/leases.py\", line 299, in _explain_not_available\n    raise NotFoundError(f'no pool features found for: {lcc.product_name}')\n"],
        "operation_id": "e72a8ca7-34cc-4e11-b80c-273592085a24"
    },
    "id": "282801b9-d612-40a5-9145-b56d8e420dac",
    "metadata": {},
    "ts": "2022-12-15T10:25:36.831673Z"
}

```

**Stack Trace**

```
"NotFoundError", "NotFoundError(no pool features found for: NVIDIA RTX Virtual Workstation)", "  File \"/venv/lib/python3.9/site-packages/nls_services_lease/controllers/lease_multi_controller.py\", line 127, in lease_multi_create
    data = _leaseMulti.lease_multi_create(event_args)
  File \"/venv/lib/python3.9/site-packages/nls_core_lease/lease_multi.py\", line 208, in lease_multi_create
    raise e
  File \"/venv/lib/python3.9/site-packages/nls_core_lease/lease_multi.py\", line 184, in lease_multi_create
    self._try_proposals(oc, mlr, results, detail)
  File \"/venv/lib/python3.9/site-packages/nls_core_lease/lease_multi.py\", line 219, in _try_proposals
    lease = self._leases.create(creator)
  File \"/venv/lib/python3.9/site-packages/nls_dal_lease_dls/leases.py\", line 230, in create
    features = self._get_features(creator)
  File \"/venv/lib/python3.9/site-packages/nls_dal_lease_dls/leases.py\", line 148, in _get_features
    self._explain_not_available(cur, creator)
  File \"/venv/lib/python3.9/site-packages/nls_dal_lease_dls/leases.py\", line 299, in _explain_not_available
    raise NotFoundError(f'no pool features found for: {lcc.product_name}')
"
```

# Nginx

- NGINX uses `/opt/certs/cert.pem` and `/opt/certs/key.pem`  
