"""One way to talk to the EPIAS Transparency Platform.

EPIAS wants a TGT ticket in a `TGT` header. A ticket stays valid for two hours,
but every route used to log in again for each request, which is what tripped
EPIAS's "too many tries" limit. epias_token() logs in once and shares the
ticket per process; epias_session() returns a requests session with the ticket,
a retry policy and a fresh login if EPIAS ever rejects the ticket.

    with epias_session() as s:
        items = s.post(url, json=payload, timeout=30).json().get('items', [])
"""
import threading
import time

import requests
from flask import current_app
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from ..functions import get_tgt_token

# Well inside the two-hour validity, so a ticket is never used near its end
TOKEN_TTL_SECONDS = 50 * 60

_token = {'value': None, 'expires': 0.0}
_token_lock = threading.Lock()


def epias_token(refresh=False):
    """The shared TGT ticket, logging in only when there is none or it is old."""
    with _token_lock:
        if refresh or not _token['value'] or time.monotonic() >= _token['expires']:
            _token['value'] = get_tgt_token(current_app.config.get('USERNAME'), current_app.config.get('PASSWORD'))
            _token['expires'] = time.monotonic() + TOKEN_TTL_SECONDS
        return _token['value']


class EpiasSession(requests.Session):
    """Session that sends the TGT header and logs in again once on a 401."""

    def request(self, method, url, **kwargs):
        response = super().request(method, url, **kwargs)
        if response.status_code == 401:
            self.headers['TGT'] = epias_token(refresh=True)
            if kwargs.get('headers') and 'TGT' in kwargs['headers']:
                kwargs['headers'] = {**kwargs['headers'], 'TGT': self.headers['TGT']}
            response = super().request(method, url, **kwargs)
        return response


def epias_session(total=5, backoff_factor=1):
    """Session for EPIAS calls: TGT header, JSON accept, retries on 429 and gateway errors.

    EPIAS data endpoints are read-only POSTs, so POST is retried too. A 500 is not
    retried: EPIAS answers bad inputs (a future date, an unknown plant) with it.
    """
    session = EpiasSession()
    session.mount('https://', HTTPAdapter(max_retries=Retry(
        total=total, backoff_factor=backoff_factor,
        status_forcelist=[429, 502, 503, 504],
        allowed_methods=['GET', 'POST'])))
    session.headers.update({'TGT': epias_token(), 'Accept': 'application/json'})
    return session
