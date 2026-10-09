#!/usr/bin/env python3
"""Backup privado antes da atualização sequencial; nunca faz deploy."""
import argparse
import datetime as dt
import fcntl
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import uuid
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]


def backup_database(db, directory):
    if not db.is_file():
        raise ValueError('SQLite ausente; a rotina exige o banco privado existente.')
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    directory.chmod(0o700)
    stamp = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    target = directory / f'painel-{stamp}-{uuid.uuid4().hex[:8]}.sqlite3'
    with Path(str(db) + '.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with sqlite3.connect(db.resolve().as_uri() + '?mode=ro', uri=True) as source:
            with sqlite3.connect(target) as destination:
                source.backup(destination)
                if destination.execute('PRAGMA quick_check').fetchall() != [('ok',)]:
                    raise ValueError('Backup SQLite não passou na verificação; atualização cancelada.')
    target.chmod(0o600)
    return target


def commands(args):
    return [
        ['npm', 'run', 'ingest', '--', '--refresh'],
        ['npm', 'run', 'ingest:history', '--', '--start', '2023-02-01', '--end', args.history_end],
        ['npm', 'run', 'ingest:expenses', '--', '--start', '2026-01-01', '--end', args.expenses_end, '--refresh'],
        ['npm', 'run', 'ingest:attendance', '--', '--year', '2026', '--refresh'],
        ['npm', 'run', 'ingest:senate-attendance', '--', '--year', '2026', '--refresh'],
        ['npm', 'run', 'ingest:photos'],
        ['npm', 'run', 'cache:photos'],
        ['npm', 'run', 'release:check'],
    ]


def update(args, root=ROOT):
    previous_umask = os.umask(0o077)
    try:
        (root / 'var').mkdir(exist_ok=True)
        with (root / 'var/update.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            backup = backup_database(root / 'var/painel.sqlite3', root / 'var/backups')
            print(f'Backup SQLite validado: {backup}', flush=True)
            env = dict(os.environ)
            env.pop('CLOUDFLARE_API_TOKEN', None)
            for command in commands(args):
                print('Executando: ' + ' '.join(command), flush=True)
                subprocess.run(command, cwd=root, env=env, check=True)
            print('Atualização concluída sem deploy. Revise os relatórios e o preview antes de npm run deploy.', flush=True)
    finally:
        os.umask(previous_umask)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--history-end', default='2026-10-05')
    parser.add_argument('--expenses-end', default='2026-09-30')
    args = parser.parse_args()
    try:
        history_end = dt.date.fromisoformat(args.history_end)
        expenses_end = dt.date.fromisoformat(args.expenses_end)
        today = dt.datetime.now(ZoneInfo('America/Sao_Paulo')).date()
        if not dt.date(2023, 2, 1) <= history_end <= today:
            raise ValueError('Fim legislativo inválido ou futuro.')
        if not dt.date(2026, 1, 1) <= expenses_end < today.replace(day=1) or (expenses_end + dt.timedelta(days=1)).day != 1:
            raise ValueError('Despesas exigem fim de mês completo anterior ao atual.')
        update(args)
    except (ValueError, OSError, sqlite3.Error, subprocess.CalledProcessError) as error:
        print(f'Atualização interrompida; nenhum deploy executado: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
