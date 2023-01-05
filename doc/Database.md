# Database structure

## `request_routing.service_instance`

| xid                                    | org_name                 |
|----------------------------------------|--------------------------|
| `10000000-0000-0000-0000-000000000000` | `lic-000000000000000000` |

- `xid` is used as `SERVICE_INSTANCE_XID`

## `request_routing.license_allotment_service_instance`

| xid                                    | service_instance_xid                   | license_allotment_xid                  |
|----------------------------------------|----------------------------------------|----------------------------------------|
| `90000000-0000-0000-0000-000000000001` | `10000000-0000-0000-0000-000000000000` | `80000000-0000-0000-0000-000000000001` |

- `xid` is only a primary-key and never used as foreign-key or reference
- `license_allotment_xid` must be used to fetch `xid`'s from `request_routing.license_allotment_reference`

## `request_routing.license_allotment_reference`

| xid                                    | license_allotment_xid                  |
|----------------------------------------|----------------------------------------|
| `20000000-0000-0000-0000-000000000001` | `80000000-0000-0000-0000-000000000001` | 

- `xid` is used as `scope_ref_list` on token request
