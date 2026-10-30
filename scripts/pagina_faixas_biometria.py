"""Monta a página de votos líquidos por faixa de biometria: injeta dados/sem_biometria/faixas.json no modelo HTML.
Uso: pagina_faixas_biometria.py <saida.html>"""
import json, os, sys
R = os.path.join(os.path.dirname(__file__), '..')
tpl = open(f'{R}/scripts/pagina_faixas_biometria.tpl.html', encoding='utf-8').read()
dados = json.dumps(json.load(open(f'{R}/dados/sem_biometria/faixas.json')), ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
html = tpl.replace('/*__DATA__*/', dados)
open(sys.argv[1], 'w', encoding='utf-8').write(html)
print(sys.argv[1], len(html) // 1024, 'KB')
