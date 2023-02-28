def load_file(filename) -> bytes:
    with open(filename, 'rb') as file:
        content = file.read()
    return content


def load_key(filename) -> "RsaKey":
    try:
        # Crypto | Cryptodome on Debian
        from Crypto.PublicKey import RSA
        from Crypto.PublicKey.RSA import RsaKey
    except ModuleNotFoundError:
        from Cryptodome.PublicKey import RSA
        from Cryptodome.PublicKey.RSA import RsaKey

    return RSA.import_key(extern_key=load_file(filename), passphrase=None)


def generate_key() -> "RsaKey":
    try:
        # Crypto | Cryptodome on Debian
        from Crypto.PublicKey import RSA
        from Crypto.PublicKey.RSA import RsaKey
    except ModuleNotFoundError:
        from Cryptodome.PublicKey import RSA
        from Cryptodome.PublicKey.RSA import RsaKey

    return RSA.generate(bits=2048)


def ha_replicate(logger: "logging.Logger", ha_replicate: str, ha_role: str, version: str, dls_url: str, dls_port: int, site_key_xid: str, instance_ref: str, origins: list, leases: list) -> bool:
    from datetime import datetime
    import httpx

    if f'{dls_url}:{dls_port}' == ha_replicate:
        logger.error(f'Failed to replicate this node ({ha_role}) to "{ha_replicate}": can\'t replicate to itself')
        return False

    data = {
        'VERSION': str(version),
        'HA_REPLICATE': f'{dls_url}:{dls_port}',
        'SITE_KEY_XID': str(site_key_xid),
        'INSTANCE_REF': str(instance_ref),
        'origins': origins,
        'leases': leases,
        'sync_timestamp': datetime.utcnow().isoformat(),
    }

    r = httpx.put(f'https://{ha_replicate}/-/ha/replicate', json=data, verify=False)
    if r.status_code == 202:
        logger.info(f'Successfully replicated this node ({ha_role}) to "{ha_replicate}".')
        return True
    logger.error(f'Failed to replicate this node ({ha_role}) to "{ha_replicate}": {r.status_code} - {r.content}')
    return False
