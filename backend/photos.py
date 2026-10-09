"""Cópias de fotos oficiais com nomes imutáveis pelo conteúdo."""
import hashlib
from backend.http import atomic_bytes


def save_image(raw, output):
    if len(raw) < 32:
        raise ValueError('Imagem incompleta')
    if raw.startswith(b'\xff\xd8\xff') and raw.rstrip().endswith(b'\xff\xd9'):
        extension = 'jpg'
    elif raw.startswith(b'\x89PNG\r\n\x1a\n') and b'IEND' in raw[-20:]:
        extension = 'png'
    else:
        raise ValueError('Resposta não é uma foto JPEG/PNG completa')
    relative = f'photos/{hashlib.sha256(raw).hexdigest()}.{extension}'
    atomic_bytes(output / relative, raw, 0o644)
    return relative
