"""
    test_build_linkcheck
    ~~~~~~~~~~~~~~~~~~~~

    Test the build process with manpage builder with the test root.

    :copyright: Copyright 2007-2020 by the Sphinx team, see AUTHORS.
    :license: BSD, see LICENSE for details.
"""

import http.server
import json
import re
import textwrap
from unittest import mock

import pytest

from utils import http_server


@pytest.mark.sphinx('linkcheck', testroot='linkcheck', freshenv=True)
def test_defaults(app):
    app.builder.build_all()

    assert (app.outdir / 'output.txt').exists()
    content = (app.outdir / 'output.txt').read_text()

    print(content)
    # looking for '#top' and '#does-not-exist' not found should fail
    assert "Anchor 'top' not found" in content
    assert "Anchor 'does-not-exist' not found" in content
    # looking for non-existent URL should fail
    assert " Max retries exceeded with url: /doesnotexist" in content
    # images should fail
    assert "Not Found for url: https://www.google.com/image.png" in content
    assert "Not Found for url: https://www.google.com/image2.png" in content
    # looking for local file should fail
    assert "[broken] path/to/notfound" in content
    assert len(content.splitlines()) == 6


@pytest.mark.sphinx('linkcheck', testroot='linkcheck', freshenv=True)
def test_defaults_json(app):
    app.builder.build_all()

    assert (app.outdir / 'output.json').exists()
    content = (app.outdir / 'output.json').read_text()
    print(content)

    rows = [json.loads(x) for x in content.splitlines()]
    row = rows[0]
    for attr in ["filename", "lineno", "status", "code", "uri",
                 "info"]:
        assert attr in row

    assert len(content.splitlines()) == 10
    assert len(rows) == 10
    # the output order of the rows is not stable
    # due to possible variance in network latency
    rowsby = {row["uri"]:row for row in rows}
    assert rowsby["https://www.google.com#!bar"] == {
        'filename': 'links.txt',
        'lineno': 10,
        'status': 'working',
        'code': 0,
        'uri': 'https://www.google.com#!bar',
        'info': ''
    }
    # looking for non-existent URL should fail
    dnerow = rowsby['https://localhost:7777/doesnotexist']
    assert dnerow['filename'] == 'links.txt'
    assert dnerow['lineno'] == 13
    assert dnerow['status'] == 'broken'
    assert dnerow['code'] == 0
    assert dnerow['uri'] == 'https://localhost:7777/doesnotexist'
    assert rowsby['https://www.google.com/image2.png'] == {
        'filename': 'links.txt',
        'lineno': 18,
        'status': 'broken',
        'code': 0,
        'uri': 'https://www.google.com/image2.png',
        'info': '404 Client Error: Not Found for url: https://www.google.com/image2.png'
    }
    # looking for '#top' and '#does-not-exist' not found should fail
    assert "Anchor 'top' not found" == \
        rowsby["https://www.google.com/#top"]["info"]
    assert "Anchor 'does-not-exist' not found" == \
        rowsby["http://www.sphinx-doc.org/en/1.7/intro.html#does-not-exist"]["info"]
    # images should fail
    assert "Not Found for url: https://www.google.com/image.png" in \
        rowsby["https://www.google.com/image.png"]["info"]


@pytest.mark.sphinx(
    'linkcheck', testroot='linkcheck', freshenv=True,
    confoverrides={'linkcheck_anchors_ignore': ["^!", "^top$"],
                   'linkcheck_ignore': [
                       'https://localhost:7777/doesnotexist',
                       'http://www.sphinx-doc.org/en/1.7/intro.html#',
                       'https://www.google.com/image.png',
                       'https://www.google.com/image2.png',
                       'path/to/notfound']
                   })
def test_anchors_ignored(app):
    app.builder.build_all()

    assert (app.outdir / 'output.txt').exists()
    content = (app.outdir / 'output.txt').read_text()

    # expect all ok when excluding #top
    assert not content

@pytest.mark.sphinx('linkcheck', testroot='linkcheck-localserver-anchor', freshenv=True)
def test_raises_for_invalid_status(app):
    class InternalServerErrorHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_error(500, "Internal Server Error")

    with http_server(InternalServerErrorHandler):
        app.builder.build_all()
    content = (app.outdir / 'output.txt').read_text()
    assert content == (
        "index.rst:1: [broken] http://localhost:7777/#anchor: "
        "500 Server Error: Internal Server Error "
        "for url: http://localhost:7777/\n"
    )


@pytest.mark.sphinx(
    'linkcheck', testroot='linkcheck', freshenv=True,
    confoverrides={'linkcheck_auth': [
                        (r'.+google\.com/image.+', 'authinfo1'),
                        (r'.+google\.com.+', 'authinfo2'),
                   ]
                  })
def test_auth(app):
    mock_req = mock.MagicMock()
    mock_req.return_value = 'fake-response'

    with mock.patch.multiple('requests', get=mock_req, head=mock_req):
        app.builder.build_all()
        for c_args, c_kwargs in mock_req.call_args_list:
            if 'google.com/image' in c_args[0]:
                assert c_kwargs['auth'] == 'authinfo1'
            elif 'google.com' in c_args[0]:
                assert c_kwargs['auth'] == 'authinfo2'
            else:
                assert not c_kwargs['auth']


@pytest.mark.sphinx(
    'linkcheck', testroot='linkcheck', freshenv=True,
    confoverrides={'linkcheck_request_headers': {
        "https://localhost:7777/": {
            "Accept": "text/html",
        },
        "http://www.sphinx-doc.org": {  # no slash at the end
            "Accept": "application/json",
        },
        "*": {
            "X-Secret": "open sesami",
        }
    }})
def test_linkcheck_request_headers(app):
    mock_req = mock.MagicMock()
    mock_req.return_value = 'fake-response'

    with mock.patch.multiple('requests', get=mock_req, head=mock_req):
        app.builder.build_all()
        for args, kwargs in mock_req.call_args_list:
            url = args[0]
            headers = kwargs.get('headers', {})
            if "https://localhost:7777" in url:
                assert headers["Accept"] == "text/html"
            elif 'http://www.sphinx-doc.org' in url:
                assert headers["Accept"] == "application/json"
            elif 'https://www.google.com' in url:
                assert headers["Accept"] == "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8"
                assert headers["X-Secret"] == "open sesami"
            else:
                assert headers["Accept"] == "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8"

def make_redirect_handler(*, support_head):
    class RedirectOnceHandler(http.server.BaseHTTPRequestHandler):
        def do_HEAD(self):
            if support_head:
                self.do_GET()
            else:
                self.send_response(405, "Method Not Allowed")
                self.end_headers()

        def do_GET(self):
            if self.path == "/?redirected=1":
                self.send_response(204, "No content")
            else:
                self.send_response(302, "Found")
                self.send_header("Location", "http://localhost:7777/?redirected=1")
            self.end_headers()

        def log_date_time_string(self):
            """Strip date and time from logged messages for assertions."""
            return ""

    return RedirectOnceHandler

@pytest.mark.sphinx('linkcheck', testroot='linkcheck-localserver', freshenv=True)
def test_follows_redirects_on_HEAD(app, capsys):
    with http_server(make_redirect_handler(support_head=True)):
        app.builder.build_all()
    stdout, stderr = capsys.readouterr()
    content = (app.outdir / 'output.txt').read_text()
    assert content == (
        "index.rst:1: [redirected with Found] "
        "http://localhost:7777/ to http://localhost:7777/?redirected=1\n"
    )
    assert stderr == textwrap.dedent(
        """\
        127.0.0.1 - - [] "HEAD / HTTP/1.1" 302 -
        127.0.0.1 - - [] "HEAD /?redirected=1 HTTP/1.1" 204 -
        """
    )

@pytest.mark.sphinx('linkcheck', testroot='linkcheck-localserver', freshenv=True)
def test_follows_redirects_on_GET(app, capsys):
    with http_server(make_redirect_handler(support_head=False)):
        app.builder.build_all()
    stdout, stderr = capsys.readouterr()
    content = (app.outdir / 'output.txt').read_text()
    assert content == (
        "index.rst:1: [redirected with Found] "
        "http://localhost:7777/ to http://localhost:7777/?redirected=1\n"
    )
    assert stderr == textwrap.dedent(
        """\
        127.0.0.1 - - [] "HEAD / HTTP/1.1" 405 -
        127.0.0.1 - - [] "GET / HTTP/1.1" 302 -
        127.0.0.1 - - [] "GET /?redirected=1 HTTP/1.1" 204 -
        """
    )
