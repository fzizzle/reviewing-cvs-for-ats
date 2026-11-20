"""render_pdf must never let a CV reach the network or run its scripts.

A local HTTP server stands in for "the internet": any request it receives means Chrome
fetched a remote resource while rendering. Loopback is the hardest case (Chrome bypasses
proxies for it by default), so blocking it shows the rules hold for real hosts too.
"""
import http.server
import pathlib
import re
import threading

import pytest

import cvlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
try:
    cvlib.find_chrome()
    HAVE_CHROME = True
except RuntimeError:
    HAVE_CHROME = False
needs_chrome = pytest.mark.skipif(not HAVE_CHROME, reason="needs Chrome/Chromium/Edge")


@pytest.fixture
def recorder():
    hits = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            hits.append(self.path)
            self.send_response(200)
            self.send_header("Content-Type", "text/css")
            self.end_headers()

        def log_message(self, *a):
            pass

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}", hits
    srv.shutdown()


@needs_chrome
def test_render_makes_no_network_requests_and_runs_no_scripts(tmp_path, recorder):
    base, hits = recorder
    html = tmp_path / "cv.html"
    html.write_text(f"""<!doctype html><html><head><meta charset="utf-8">
<link rel="stylesheet" href="{base}/link.css">
<style>@import url('{base}/import.css'); body {{ background: url('{base}/bg.png'); }}</style>
</head><body><p>Jane Example</p>
<img src="{base}/img.png">
<img src="http://localhost:{base.rsplit(':', 1)[1]}/byname.png">
<p id="js">JS DID NOT RUN</p>
<script>document.getElementById('js').textContent = 'JS RAN';
fetch('{base}/fetch'); new Image().src = '{base}/beacon';</script>
</body></html>""", encoding="utf-8")
    pdf = cvlib.render_pdf(html, tmp_path / "cv.pdf")
    import pymupdf
    text = "".join(p.get_text() for p in pymupdf.open(pdf))
    assert hits == []
    assert "JS DID NOT RUN" in text and "JS RAN" not in text


def test_template_loads_no_remote_resources():
    src = (ROOT / "templates" / "cv-template.html").read_text(encoding="utf-8")
    # Clickable <a href> links are fine (never fetched); anything that loads a resource is not.
    loaders = re.findall(r"@import|url\(\s*['\"]?https?:|src\s*=\s*['\"]?https?:|<link[^>]+https?:", src, re.I)
    assert loaders == []
