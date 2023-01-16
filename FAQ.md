# FAQ

## `Failed to acquire license from <ip> (Info: <license> - Error: The allowed time to process response has expired)`

- Did your timezone settings are correct on fastapi-dls **and your guest**?

- Did you download the client-token more than an hour ago?

Please download a new client-token. The guest have to register within an hour after client-token was created.


## `jose.exceptions.JWTError: Signature verification failed.`

- Did you recreated `instance.public.pem` / `instance.private.pem`?

Then you have to download a **new** client-token on each of your guests.

