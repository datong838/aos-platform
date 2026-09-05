"""Offline test-only Registry V2 reader. No upload, auth or production use."""
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import hashlib

ROOT=Path('/fixture')
MANIFEST=(ROOT/'manifest.json').read_bytes()
DIGEST='sha256:'+hashlib.sha256(MANIFEST).hexdigest()


class Handler(BaseHTTPRequestHandler):
    def do_HEAD(self):
        self.respond(False)

    def do_GET(self):
        self.respond(True)

    def respond(self, body):
        if self.path=='/v2/':
            raw,kind=b'{}','application/json'
        elif self.path in ('/v2/aos-test/manifests/latest','/v2/aos-test/manifests/'+DIGEST):
            raw,kind=MANIFEST,'application/vnd.oci.image.manifest.v1+json'
        elif self.path.startswith('/v2/aos-test/blobs/sha256:'):
            value=self.path.rsplit(':',1)[-1]
            if len(value)!=64 or any(c not in '0123456789abcdef' for c in value):
                self.send_error(404); return
            path=ROOT/'blobs'/value
            if not path.is_file():
                self.send_error(404); return
            raw,kind=path.read_bytes(),'application/octet-stream'
        else:
            self.send_error(404); return
        self.send_response(200)
        self.send_header('Content-Type',kind)
        self.send_header('Content-Length',str(len(raw)))
        self.send_header('Docker-Distribution-Api-Version','registry/2.0')
        if kind=='application/vnd.oci.image.manifest.v1+json':
            self.send_header('Docker-Content-Digest',DIGEST)
        self.end_headers()
        if body:self.wfile.write(raw)

    def log_message(self,*args):
        pass


if __name__=='__main__':
    HTTPServer(('0.0.0.0',5000),Handler).serve_forever()
