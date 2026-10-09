#!/usr/bin/env python3
"""Consulta fontes oficiais para preparar recortes; não publica indicadores."""
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.http import HttpCache


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--month', type=int, choices=range(1, 13))
    source.add_argument('--diary', type=int)
    source.add_argument('--votes', help='Data inicial YYYY-MM-DD')
    parser.add_argument('--end', help='Data final da consulta de votos')
    parser.add_argument('--pages', type=int, nargs=2, metavar=('INICIO', 'FIM'))
    parser.add_argument('--offline', action='store_true')
    args = parser.parse_args()

    def fetch(url):
        request = urllib.request.Request(url, headers={'User-Agent': 'PainelPolitico/0.5', 'Accept': 'application/json,application/pdf,text/html'})
        with urllib.request.urlopen(request, timeout=25) as response:
            return response.read()

    cache = HttpCache(ROOT / 'var/cache', fetch=fetch, ttl=86400)

    def read(url):
        path = cache.directory / (hashlib.sha256(url.encode()).hexdigest() + '.bin')
        raw = path.read_bytes() if args.offline else cache.get(url)
        print(json.dumps({'fonte': url, 'arquivo': str(path), 'sha256': hashlib.sha256(raw).hexdigest(),
                          'coletadoEm': dt.datetime.fromtimestamp(path.stat().st_mtime, dt.timezone.utc).isoformat()}, ensure_ascii=False), flush=True)
        return raw, path

    base = 'https://legis.senado.leg.br'
    if args.month:
        raw, _ = read(f'{base}/diarios/resources/calendario-html?mes={args.month}&ano=2026&veiculo=1&tipo=2')
        print(raw.decode())
    elif args.votes:
        end = args.end or args.votes
        if dt.date.fromisoformat(args.votes) > dt.date.fromisoformat(end):
            parser.error('Período de votos inválido')
        raw, _ = read(f'{base}/dadosabertos/votacao?dataInicio={args.votes}&dataFim={end}&v=2')
        for vote in json.loads(raw):
            print(json.dumps({k: v for k, v in vote.items() if k != 'votos'}, ensure_ascii=False))
    else:
        raw, _ = read(f'{base}/diarios/ver/{args.diary}')
        match = re.search(r'var diario = (\{.*?\});', raw.decode())
        if not match:
            raise ValueError('Metadados do Diário ausentes')
        metadata = json.loads(match[1])
        print(json.dumps(metadata, ensure_ascii=False))
        if metadata['caderno']['emElaboracao']:
            raise ValueError('Diário ainda em elaboração')
        start, end = args.pages or [metadata['paginacao']['sequenciaSumarioInicio'], metadata['paginacao']['sequenciaSumarioFim']]
        if not 1 <= start <= end <= metadata['caderno']['qtdPaginas'] or end - start >= 20:
            raise ValueError('Intervalo inválido: consulte até vinte páginas por vez')
        _, path = read(f'{base}/diarios/BuscaPaginasDiario?codDiario={args.diary}&download=true&paginaInicial={start}&paginaFinal={end}')
        text = subprocess.run(['pdftotext', '-layout', str(path), '-'], check=True, capture_output=True).stdout.decode()
        print(text)


if __name__ == '__main__':
    main()
