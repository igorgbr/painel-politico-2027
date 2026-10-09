"""Cache privado de respostas completas e paginação com retomada por URL."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time
import urllib.request
from urllib.parse import urljoin, urlparse


def atomic_bytes(path, raw, mode=0o600):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            os.chmod(temporary, mode)
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()


def atomic_json(path, value, mode=0o600):
    atomic_bytes(path, (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode(), mode)


def read_url(url):
    for attempt in range(3):
        try:
            request = urllib.request.Request(url, headers={'User-Agent': 'PainelPolitico/0.2'})
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.read()
        except Exception:
            if attempt == 2:
                raise
            time.sleep(attempt + 1)


class HttpCache:
    def __init__(self, directory, fetch=read_url, ttl=3600):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.directory.chmod(0o700)
        self.fetch = fetch
        self.ttl = ttl

    def get(self, url, refresh=False):
        key = hashlib.sha256(url.encode()).hexdigest()
        path = self.directory / (key + '.bin')
        if not refresh and path.exists() and time.time() - path.stat().st_mtime < self.ttl:
            return path.read_bytes()
        # Falhas de rede nunca são disfarçadas como uma resposta antiga atualizada.
        raw = self.fetch(url)
        atomic_bytes(path, raw)
        return raw

    def invalidate(self, url):
        (self.directory / (hashlib.sha256(url.encode()).hexdigest() + '.bin')).unlink(missing_ok=True)

    def pages(self, url, refresh=False):
        visited = set()
        origin = urlparse(url)
        while url:
            target = urlparse(url)
            if target.scheme != origin.scheme or target.netloc != origin.netloc or url in visited:
                raise ValueError('Paginação circular ou fora da origem')
            visited.add(url)
            try:
                payload = json.loads(self.get(url, refresh=refresh))
                if not isinstance(payload.get('dados'), list) or not isinstance(payload.get('links', []), list):
                    raise ValueError('Schema de paginação incompatível')
                next_links = [link['href'] for link in payload.get('links', []) if link.get('rel') == 'next']
                if len(next_links) > 1:
                    raise ValueError('Paginação ambígua')
            except (ValueError, KeyError, TypeError):
                self.invalidate(url)
                raise
            yield payload['dados']
            url = urljoin(url, next_links[0]) if next_links else None
