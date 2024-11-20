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
            body = body.decode()
            try:
                json.loads(body)
            except json.decoder.JSONDecodeError:
                logger.warning(f'Malformed json received! Try to fix it, "PatchMalformedJsonMiddleware" is enabled.')
                s = PatchMalformedJsonMiddleware.fix_json(body)
                logger.debug(f'Fixed JSON: "{s}"')
                s = json.loads(s)  # ensure json is now valid
                # set new body
                request._body = json.dumps(s).encode('utf-8')

        response = await call_next(request)
        return response

    @staticmethod
    def fix_json(s: str) -> str:
        s = s.replace('\t', '')
        s = s.replace('\n', '')
        return re.sub(PatchMalformedJsonMiddleware.REGEX, r'\1"\2', s)
