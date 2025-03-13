# Reverse Engineering Notes

[[_TOC_]]

# NLS Docker Stack

- More about Docker Images https://git.collinwebdesigns.de/nvidia/nls

## Appliance

### Configuration data

- Most variables and configs are stored in `/var/lib/docker/volumes/configurations/_data`.
- Config-Variables are in `etc/dls/config/service_env.conf`.

### NLS Logs

Logs are found in `/var/lib/docker/volumes/logs/_data`.

Most interesting logs are:

- `fileInstallation.log`
- `serviceInstance.log`

### File manipulation and copy

- Files can be copied with `docker cp <container-id>:/venv/... /opt/localfile/...`.
- Files can be directly edited via Docker-Volume mounts
  - see `df -h` (one is nls, the other postgres container)
    ```
    overlay   16G   11G  5.6G  66% /var/lib/docker/overlay2/<hash>/merged
    overlay    16G   11G  5.6G  66% /var/lib/docker/overlay2/<hash>/merged
    ```
  - then you can edit files with e.g. `nano venv/lib/python3.12/site-packages/...`

### Other tools / files

Other tools / files which may can helpful, but not known for what they are used.

- `/etc/dls/config/decryptor/decryptor`
- `/etc/dls/config/site_key_uri.bin`
- `/etc/dls/config/dls_db_password.bin`

## Database

- It's enough to manipulate database licenses. There must not be changed any line of code to bypass licensing
  validations.

Valid users are `dls_writer` and `postgres`.

```shell
docker exec -it <dls:pgsql> psql -h localhost -U postgres
```

If you want external access to database, you have to add `ports: [ 5432:5432 ]` to postgres section in
`docker-compose.yml`.
Then you can *exec* into container with `psql` and add a new superuser:

```sql
CREATE
USER admin WITH LOGIN SUPERUSER PASSWORD 'admin';
```

# Logging / Stack Trace

- https://docs.nvidia.com/license-system/latest/nvidia-license-system-user-guide/index.html#troubleshooting-dls-instance


# Nginx

- NGINX uses `/opt/certs/cert.pem` and `/opt/certs/key.pem`  

# Usefully commands on Client

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
systemd: Started NVIDIA Grid Daemon.
nvidia-gridd: Configuration parameter ( ServerAddress  ) not set
nvidia-gridd: vGPU Software package (0)
nvidia-gridd: Ignore service provider and node-locked licensing
nvidia-gridd: NLS initialized
nvidia-gridd: Acquiring license. (Info: license.nvidia.space; NVIDIA RTX Virtual Workstation)
nvidia-gridd: License acquired successfully. (Info: license.nvidia.space, NVIDIA RTX Virtual Workstation; Expiry: 2023-1-29 22:3:0 GMT)
```
