# FastAPI-DLS

Minimal Licencing Servie.

## Installation

**The token file has to be copied! It's not enough to C&P file contents, because there can be special characters.**

### Linux

```shell
curl --insecure -X GET https://<hostname-or-ip-address>/client-token -o /etc/nvidia/ClientConfigToken/client_configuration_token.tok
service nvidia-gridd restart
nvidia-smi -q | grep "License"
```

### Windows

Download file and place it into `:\Program Files\NVIDIA Corporation\vGPU Licensing\ClientConfigToken`.
Now restart `NvContainerLocalSystem` service. 
