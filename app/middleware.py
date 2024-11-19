import json
import logging
import re

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger = logging.getLogger(__name__)


class PatchMalformedJsonMiddleware(BaseHTTPMiddleware):
    # see oscar.krause/fastapi-dls#1

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
                body = body.replace('\t', '')
                body = body.replace('\n', '')

                regex = '(\"mac_address_list\"\:\s?\[)([\w\d])'
                s = re.sub(regex, r'\1"\2', body)
                logger.debug(f'Fixed JSON: "{s}"')
                s = json.loads(s)  # ensure json is now valid

                # set new body
                request._body = json.dumps(s).encode('utf-8')

        response = await call_next(request)
        return response
