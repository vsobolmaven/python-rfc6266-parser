# coding: utf-8
from rfc6266_parser import (
    parse_headers, parse_requests_response,
    build_header)
import pytest


def test_parsing():
    assert parse_headers(None).disposition == 'inline'
    assert parse_headers('attachment').disposition == 'attachment'
    assert parse_headers('attachment; key=val').assocs['key'] == 'val'
    assert parse_headers(
        'attachment; filename=simple').filename_unsafe == 'simple'

    fname = parse_headers(
        b'attachment; filename="oy\xe9"'.decode('latin-1')
    ).filename_unsafe
    assert fname == u'oyé', repr(fname)

    cd = parse_headers(
        'attachment; filename="EURO rates";'
        ' filename*=utf-8\'\'%e2%82%ac%20rates')
    assert cd.filename_unsafe == u'€ rates'


@pytest.mark.skipif("(3,0) <= sys.version_info < (3,3)")
def test_requests(httpserver):
    requests = pytest.importorskip('requests')
    httpserver.serve_content('eep', headers={
        'Content-Disposition': 'attachment; filename="a b="'})
    resp = requests.get(httpserver.url)
    assert parse_requests_response(resp).filename_unsafe == 'a b='


def test_location_fallback():
    assert parse_headers(
        None, location='https://foo/bar%c3%a9.py'
    ).filename_unsafe == u'baré.py'

    assert parse_headers(
        None, location='https://foo/'
    ).filename_unsafe == u''

    assert parse_headers(
        None, location='https://foo/%C3%A9toil%C3%A9/'
    ).filename_unsafe == u'étoilé'


def test_relaxed():
    assert parse_headers('attachment;').disposition == 'attachment'
    assert parse_headers('attachment; key=val;').disposition == 'attachment'
    cd = parse_headers('attachment; filename="spa  ced";')
    assert cd.filename_unsafe == u'spa ced'


@pytest.mark.parametrize("name", [
    'a b', 'a b ', ' a b', 'a\"b', u'aéio o♥u"qfsdf!'
])
def test_roundtrip(name):
    header = build_header(name)
    header = parse_headers(header)
    assert header.filename_unsafe == name
