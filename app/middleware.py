import json
import logging
import re

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger = logging.getLogger(__name__)


class PatchMalformedJsonMiddleware(BaseHTTPMiddleware):
    # see oscar.krause/fastapi-dls#1

    REGEX = '(\"mac_address_list\"\:\s?\[)([\w\d])'

    def __init__(self, app, enabled: bool):
        super().__init__(app)
        self.enabled = enabled

    async def dispatch(self, request: Request, call_next):
        body = await request.body()
        content_type = request.headers.get('Content-Type')

        if self.enabled and content_type == 'application/json':
            logger.debug(f'Using Request-Patch because "PatchMalformedJsonMiddleware" is enabled!')
            body = body.decode()

            # try to fix json
            try:
                j = json.loads(body)
                self.__fix_mac_address_list_length(j=j, size=1)
            except json.decoder.JSONDecodeError:
                logger.warning(f'Malformed json received! Try to fix it.')
                body = PatchMalformedJsonMiddleware.fix_json(body)
                logger.debug(f'Fixed JSON: "{body}"')
                j = json.loads(body)  # ensure json is now valid
                j = self.__fix_mac_address_list_length(j=j, size=1)
                # set new body
                request._body = json.dumps(j).encode('utf-8')

        response = await call_next(request)
        return response

    @staticmethod
    def __fix_mac_address_list_length(j: dict, size: int = 1) -> dict:
        # reduce "mac_address_list" to
        environment = j.get('environment', {})
        fingerprint = environment.get('fingerprint', {})
        mac_address = fingerprint.get('mac_address_list', [])

        if len(mac_address) > 0:
            logger.info(f'Transforming "mac_address_list" to length of {size}.')
            j['environment']['fingerprint']['mac_address_list'] = mac_address[:size]

        return j

    @staticmethod
    def fix_json(s: str) -> str:
        s = s.replace('\t', '')
        s = s.replace('\n', '')
        return re.sub(PatchMalformedJsonMiddleware.REGEX, r'\1"\2', s)
