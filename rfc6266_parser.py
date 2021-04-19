# vim: set fileencoding=utf-8 sw=4 ts=4 et :

"""Implements RFC 6266, the Content-Disposition HTTP header.
parse_headers handles the receiver side.
It has shortcuts for some http libraries:
    parse_httplib2_response and parse_requests_response.
It returns a ContentDisposition object with attributes like is_inline,
filename_unsafe, filename_sanitized.
build_header handles the sender side.
"""

from collections import namedtuple
from string import ascii_letters, digits
from werkzeug.http import parse_options_header

import posixpath
import os.path
import sys

__all__ = (
    'ContentDisposition',
    'parse_headers',
    'parse_httplib2_response',
    'parse_requests_response',
    'build_header',
)

PY3K = sys.version_info >= (3,)

LangTagged = namedtuple('LangTagged', 'string langtag')

if PY3K:
    from urllib.parse import urlsplit, unquote, quote

    xrange = range
    # XXX Both implementations allow stray %

    def percent_encode(string, safe, encoding):
        return quote(string, safe, encoding, errors='strict')

    def percent_decode(string, encoding):
        # unquote doesn't default to strict, fix that
        return unquote(string, encoding, errors='strict')

else:
    from urllib import quote, unquote
    from urlparse import urlsplit

    def percent_encode(string, **kwargs):
        encoding = kwargs.pop('encoding')
        return quote(string.encode(encoding), **kwargs)

    def percent_decode(string, **kwargs):
        encoding = kwargs.pop('encoding')
        return unquote(string, **kwargs).decode(encoding)


class ContentDisposition(object):
    """
    Records various indications and hints about content disposition.
    These can be used to know if a file should be downloaded or
    displayed directly, and to hint what filename it should have
    in the download case.
    """

    def __init__(self, disposition='inline', assocs=None, location=None):
        """This constructor is used internally after parsing the header.
        Instances should generally be created from a factory
        function, such as parse_headers and its variants.
        :type disposition: str
        """

        self.disposition = disposition
        self.location = location
        if assocs is None:
            self.assocs = {}
        else:
            # XXX Check that parameters aren't repeated
            self.assocs = dict((key.lower(), assocs[key]) for key in assocs)

    @property
    def filename_unsafe(self):
        """The filename from the Content-Disposition header.
        If a location was passed at instanciation, the basename
        from that may be used as a fallback. Otherwise, this may
        be the None value.
        On safety:
            This property records the intent of the sender.
            You shouldn't use this sender-controlled value as a filesystem
        path, it can be insecure. Serving files with this filename can be
        dangerous as well, due to a certain browser using the part after the
        dot for mime-sniffing.
        Saving it to a database is fine by itself though.
        """
        if 'filename' in self.assocs:
            # XXX Reject non-ascii (parsed via qdtext) here?
            return self.assocs['filename']
        elif self.location is not None:
            return posixpath.basename(self.location_path.rstrip('/'))

    @property
    def location_path(self):
        if self.location:
            return percent_decode(
                urlsplit(self.location, scheme='http').path,
                encoding='utf-8')

    def filename_sanitized(self, extension, default_filename='file'):
        """Returns a filename that is safer to use on the filesystem.
        The filename will not contain a slash (nor the path separator
        for the current platform, if different), it will not
        start with a dot, and it will have the expected extension.
        No guarantees that makes it "safe enough".
        No effort is made to remove special characters;
        using this value blindly might overwrite existing files, etc.
        """

        assert extension
        assert extension[0] != '.'
        assert default_filename
        assert '.' not in default_filename
        extension = '.' + extension

        fname = self.filename_unsafe
        if fname is None:
            fname = default_filename
        fname = posixpath.basename(fname)
        fname = os.path.basename(fname)
        fname = fname.lstrip('.')
        if not fname:
            fname = default_filename
        if not fname.endswith(extension):
            fname = fname + extension
        return fname

    @property
    def is_inline(self):
        """If this property is true, the file should be handled inline.
        Otherwise, and unless your application supports other dispositions
        than the standard inline and attachment, it should be handled
        as an attachment.
        """

        return self.disposition.lower() == 'inline'

    def __repr__(self):
        return 'ContentDisposition(%r, %r, %r)' % (
            self.disposition, self.assocs, self.location)


def ensure_charset(text, encoding):
    if isinstance(text, bytes):
        return text.decode(encoding)
    else:
        assert fits_inside_codec(text, encoding)
        return text


def parse_headers(content_disposition, location=None):
    """Build a ContentDisposition from header values.
    :type content_disposition: str|unicode|None
    :type location: str
    :rtype: ContentDisposition
    """

    if content_disposition is None:
        return ContentDisposition(location=location)

    disposition, params = parse_options_header(normalize_ws(content_disposition))

    return ContentDisposition(
        disposition=disposition, assocs=params, location=location)


def parse_httplib2_response(response):
    """Build a ContentDisposition from an httplib2 response.
    """

    return parse_headers(
        response.get('content-disposition'), response['content-location'])


def parse_requests_response(response):
    """Build a ContentDisposition from a requests (PyPI) response.
    """

    return parse_headers(
        response.headers.get('content-disposition'), response.url)


# RFC 2616
separator_chars = "()<>@,;:\\\"/[]?={} \t"
ctl_chars = ''.join(chr(i) for i in xrange(32)) + chr(127)
nontoken_chars = separator_chars + ctl_chars

# RFC 5987
attr_chars_nonalnum = '!#$&+-.^_`|~'
attr_chars = ascii_letters + digits + attr_chars_nonalnum

# RFC 5987 gives this alternative construction of the token character class
token_chars = attr_chars + "*'%"


def is_token_char(ch):
    # Must be ascii, and neither a control char nor a separator char
    asciicode = ord(ch)
    # < 128 means ascii, exclude control chars at 0-31 and 127,
    # exclude separator characters.
    return 31 < asciicode < 127 and ch not in separator_chars


def usesonlycharsfrom(candidate, chars):
    # Found that shortcut in urllib.quote
    return candidate.rstrip(chars) == ''


def is_token(candidate):
    # return usesonlycharsfrom(candidate, token_chars)
    return all(is_token_char(ch) for ch in candidate)


def is_ascii(text):
    return all(ord(ch) < 128 for ch in text)


def fits_inside_codec(text, codec):
    try:
        text.encode(codec)
    except UnicodeEncodeError:
        return False
    else:
        return True


def is_lws_safe(text):
    return normalize_ws(text) == text


def normalize_ws(text):
    return ' '.join(text.split())


def qd_quote(text):
    return text.replace('\\', '\\\\').replace('"', '\\"')


def build_header(
        filename, disposition='attachment', filename_compat=None
):
    """Generate a Content-Disposition header for a given filename.
    For legacy clients that don't understand the filename* parameter,
    a filename_compat value may be given.
    It should either be ascii-only (recommended) or iso-8859-1 only.
    In the later case it should be a character string
    (unicode in Python 2).
    Options for generating filename_compat (only useful for legacy clients):
    - ignore (will only send filename*);
    - strip accents using unicode's decomposing normalisations,
    which can be done from unicode data (stdlib), and keep only ascii;
    - use the ascii transliteration tables from Unidecode (PyPI);
    - use iso-8859-1
    Ignore is the safest, and can be used to trigger a fallback
    to the document location (which can be percent-encoded utf-8
    if you control the URLs).
    See https://tools.ietf.org/html/rfc6266#appendix-D
    :type disposition: str|unicode
    :type filename: str|unicode

    :rtype: bytes
    """

    # While this method exists, it could also sanitize the filename
    # by rejecting slashes or other weirdness that might upset a receiver.

    if disposition != 'attachment':
        assert is_token(disposition)

    rv = disposition

    if is_token(filename):
        rv += '; filename=%s' % (filename,)
        return rv.encode('iso-8859-1')
    elif is_ascii(filename) and is_lws_safe(filename):
        qd_filename = qd_quote(filename)
        rv += '; filename="%s"' % (qd_filename,)
        if qd_filename == filename:
            # RFC 6266 claims some implementations are iffy on qdtext's
            # backslash-escaping, we'll include filename* in that case.
            return rv.encode('iso-8859-1')
    elif filename_compat:
        if is_token(filename_compat):
            rv += '; filename=%s' % (filename_compat,)
        else:
            assert is_lws_safe(filename_compat)
            rv += '; filename="%s"' % (qd_quote(filename_compat),)

    # alnum are already considered always-safe, but the rest isn't.
    # Python encodes ~ when it shouldn't, for example.
    rv += "; filename*=utf-8''%s" % (percent_encode(
        filename, safe=attr_chars_nonalnum, encoding='utf-8'),)

    # This will only encode filename_compat, if it used non-ascii iso-8859-1.
    return rv.encode('iso-8859-1')
