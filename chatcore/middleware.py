import json
import re

from django.utils.deprecation import MiddlewareMixin

SKIP_PREFIXES = (
    '/api/v1/errors',
    '/static/',
    '/favicon.ico',
)

MAX_DETAIL_CHARS = 100_000


def _summarize(body, status_code, path):
    if not body:
        return f'HTTP {status_code} {path}'
    try:
        data = json.loads(body)
        if isinstance(data, dict):
            detail = data.get('detail') or data.get('error')
            if detail:
                return str(detail)[:500]
    except (TypeError, ValueError):
        pass
    title = re.search(r'<title>([^<]+)</title>', body, re.IGNORECASE)
    if title:
        return title.group(1).strip()[:500]
    plain = re.sub(r'<[^>]+>', ' ', body)
    plain = re.sub(r'\s+', ' ', plain).strip()
    return (plain[:300] if plain else f'HTTP {status_code} {path}')


class ErrorLogMiddleware(MiddlewareMixin):
    """Persist HTTP 5xx responses so they can be reviewed in the admin UI."""

    def process_response(self, request, response):
        try:
            self._maybe_log(request, response)
        except Exception:
            pass
        return response

    def _maybe_log(self, request, response):
        if getattr(response, 'status_code', 0) < 500:
            return
        path = request.path or ''
        if any(path.startswith(prefix) for prefix in SKIP_PREFIXES):
            return

        body = ''
        try:
            content = getattr(response, 'content', b'') or b''
            body = content.decode('utf-8', errors='replace')[:MAX_DETAIL_CHARS]
        except Exception:
            body = ''

        from .models import ErrorLog

        ErrorLog.objects.create(
            method=(request.method or '')[:10],
            path=path[:500],
            status_code=response.status_code,
            message=_summarize(body, response.status_code, path),
            detail=body,
            content_type=(response.get('Content-Type') or '')[:120],
        )
