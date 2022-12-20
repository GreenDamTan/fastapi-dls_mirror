# FastAPI-DLS

Minimal Delegated License Service (DLS).

# Setup (Docker)

**Run this on the Docker-Host**

```shell
WORKING_DIR=/opt/docker/fastapi-dls/cert
mkdir -p $WORKING_DIR
cd $WORKING_DIR
openssl genrsa -out $WORKING_DIR/instance.private.pem 2048 
openssl rsa -in $WORKING_DIR/instance.private.pem -outform PEM -pubout -out $WORKING_DIR/instance.public.pem
openssl req -x509 -nodes -days 3650 -newkey rsa:2048 -keyout  $WORKING_DIR/webserver.key -out $WORKING_DIR/webserver.crt
docker run -e DLS_URL=`hostname -i` -e DLS_PORT=443 -p 443:443 -v $WORKING_DIR:/app/cert collinwebdesigns/fastapi-dls:latest
```

# Installation

**The token file has to be copied! It's not enough to C&P file contents, because there can be special characters.**

## Linux

```shell
curl --insecure -X GET https://<dls-hostname-or-ip>/client-token -o /etc/nvidia/ClientConfigToken/client_configuration_token.tok
service nvidia-gridd restart
nvidia-smi -q | grep "License"
```

## Windows

Download file and place it into `C:\Program Files\NVIDIA Corporation\vGPU Licensing\ClientConfigToken`.
Now restart `NvContainerLocalSystem` service.

# Troubleshoot

## Linux

Logs are available with `journalctl -u nvidia-gridd -f`.

## Windows

Logs are available in `C:\Users\Public\Documents\Nvidia\LoggingLog.NVDisplay.Container.exe.log`.

# Known Issues

## Linux

Currently, there are no known issues.

## Windows

On Windows there is currently a problem returning the license. As you can see the license is installed successfully
after
a few minutes. About the time of the first *lease period* the driver gets a *Mismatch between client and server with
respect to licenses held*.

<details>
  <summary>Log</summary>

```
Tue Dec 20 05:55:52 2022:<2>:NLS initialized
Tue Dec 20 05:55:57 2022:<2>:Mismatch between client and server with respect to licenses held. Returning the licenses
Tue Dec 20 05:55:58 2022:<2>:License returned successfully. (Info: 192.168.178.33)
Tue Dec 20 05:56:20 2022:<2>:Mismatch between client and server with respect to licenses held. Returning the licenses
Tue Dec 20 05:56:21 2022:<2>:License returned successfully. (Info: 192.168.178.33)
Tue Dec 20 05:56:46 2022:<2>:Mismatch between client and server with respect to licenses held. Returning the licenses
Tue Dec 20 05:56:47 2022:<2>:License returned successfully. (Info: 192.168.178.33)
Tue Dec 20 05:56:54 2022:<1>:License renewed successfully. (Info: 192.168.178.33, NVIDIA RTX Virtual Workstation; Expiry: 2022-12-20 5:11:54 GMT)
Tue Dec 20 05:57:17 2022:<2>:Mismatch between client and server with respect to licenses held. Returning the licenses
Tue Dec 20 05:57:18 2022:<2>:License returned successfully. (Info: 192.168.178.33)
Tue Dec 20 05:59:20 2022:<1>:License renewed successfully. (Info: 192.168.178.33, NVIDIA RTX Virtual Workstation; Expiry: 2022-12-20 5:14:20 GMT)
Tue Dec 20 06:01:45 2022:<1>:License renewed successfully. (Info: 192.168.178.33, NVIDIA RTX Virtual Workstation; Expiry: 2022-12-20 5:16:45 GMT)
Tue Dec 20 06:04:10 2022:<1>:License renewed successfully. (Info: 192.168.178.33, NVIDIA RTX Virtual Workstation; Expiry: 2022-12-20 5:19:10 GMT)
```

</details>
