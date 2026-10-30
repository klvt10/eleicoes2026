"""Decodificador BER mínimo (suficiente para o boletim de urna do TSE)."""

def read_tlv(b, i):
    t = b[i]; i += 1
    cls, cons, tag = t >> 6, (t >> 5) & 1, t & 0x1f
    if tag == 0x1f:
        tag = 0
        while True:
            x = b[i]; i += 1
            tag = (tag << 7) | (x & 0x7f)
            if not x & 0x80: break
    L = b[i]; i += 1
    if L & 0x80:
        n = L & 0x7f
        L = int.from_bytes(b[i:i+n], 'big'); i += n
    return cls, cons, tag, b[i:i+L], i + L

def parse(b):
    """Retorna lista de nós (cls, tag, valor|filhos)."""
    out, i = [], 0
    while i < len(b):
        cls, cons, tag, v, i = read_tlv(b, i)
        out.append((cls, tag, parse(v) if cons else v))
    return out

def dump(nodes, d=0):
    for cls, tag, v in nodes:
        if isinstance(v, list):
            print('  '*d + f'[{cls}:{tag}]'); dump(v, d+1)
        else:
            s = v.decode('latin1') if all(32 <= c < 127 for c in v) and v else v.hex()
            if cls == 0 and tag in (2, 10): s = int.from_bytes(v, 'big', signed=True)
            print('  '*d + f'[{cls}:{tag}] {s}')
