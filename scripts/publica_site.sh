#!/bin/bash
# Publica o site no Netlify com um número de versão novo nos endereços de app.js, app.css e dados
# (evita o navegador misturar código novo com dados antigos do cache).
set -e
cd "$(dirname "$0")/../site"
V=$(date +%Y%m%d%H%M%S)
sed -i "s/const VERSAO = '[^']*'/const VERSAO = '$V'/" app.js
sed -i "s/app\.css?v=[^\"]*/app.css?v=$V/; s/app\.js?v=[^\"]*/app.js?v=$V/" index.html
sed -i "s/const VERSAO = '[^']*'/const VERSAO = '$V'/" comparativo.js
sed -i "s/const VERSAO = '[^']*'/const VERSAO = '$V'/" modelo.js
sed -i "s/const VERSAO = '[^']*'/const VERSAO = '$V'/" votos-por-urna.js
sed -i "s/app\.css?v=[^\"]*/app.css?v=$V/; s/votos-por-urna\.js?v=[^\"]*/votos-por-urna.js?v=$V/" votos-por-urna.html
sed -i "s/app\.css?v=[^\"]*/app.css?v=$V/; s/cards\.css?v=[^\"]*/cards.css?v=$V/; s/cards\.js?v=[^\"]*/cards.js?v=$V/; s/comparativo\.js?v=[^\"]*/comparativo.js?v=$V/; s/modelo\.js?v=[^\"]*/modelo.js?v=$V/" comparativo.html modelo.html
npx netlify-cli@17.38.1 deploy --prod --dir . --message "${1:-publicação $V}"
echo "versão $V"
