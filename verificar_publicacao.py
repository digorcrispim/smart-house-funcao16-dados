"""Verificação independente das superfícies públicas do Smart House, sem credenciais."""
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import tempfile
import time
import unicodedata
import urllib.parse as url
import urllib.request as http
from contextlib import closing

VERSAO = 'v2026.11.16.3'
RELEASE = f'https://github.com/digorcrispim/smart-house-funcao16-dados/releases/download/{VERSAO}/'
PORTAL = 'https://sites.google.com/view/smart-house-funcao16-pmsp/'
PRODUCAO = 'https://smart-house-funcao16-pmsp.streamlit.app/'
ROTAS = {
    'institucional': 'Institucional', 'financeira': 'Financeira',
    'orcamentaria': 'Orçamentária', 'juridica': 'Jurídica',
    'territorial': 'Territorial', 'fisica': 'Física',
}
CONTROLES = [
    ("""SELECT count(*), count(DISTINCT id), count(DISTINCT nota),
        sum(pago_exercicio),sum(pago_restos),sum(pago) FROM macro_fato
        WHERE nivel='nota' AND contrato IN (
        SELECT sof FROM instrumento_sof WHERE instrumento='GI:187')""",
     (476, 476, 476, 48154327260, 7366247379, 55520574639)),
    ("""SELECT count(*),sum(se),sum(si),sum(se AND si) FROM (
        SELECT (coalesce(trim(obra),'')='' AND coalesce(trim(projeto),'')='') se,
        tem_instrumento=0 si FROM intervencoes WHERE posicao='uniao')""",
     (221, 46, 46, 29)),
    ("""SELECT count(*),sum(pago),count(DISTINCT posicao),min(posicao)
        FROM macro_fato WHERE nivel='dotacao' AND exercicio='2026'""",
     (321, 239336911898, 1, '2026-10-31 23:59:59')),
]


class Falha(Exception):
    """Mensagem fixa adequada a um log público."""


def exigir(condicao, mensagem):
    if not condicao:
        raise Falha(mensagem)


def log(texto):
    print(texto, flush=True)
    if destino := os.getenv('GITHUB_STEP_SUMMARY'):
        with open(destino, 'a', encoding='utf-8') as arquivo:
            arquivo.write('- ' + texto + '\n')


def conferir_banco(arquivo):
    with closing(sqlite3.connect(arquivo.resolve().as_uri() + '?mode=ro&immutable=1', uri=True)) as banco:
        exigir(banco.execute('PRAGMA quick_check').fetchall() == [('ok',)], 'Integridade SQLite divergente.')
        exigir(banco.execute('PRAGMA user_version').fetchone() == (1,), 'Versão de esquema divergente.')
        for nome, (consulta, esperado) in zip(('financeiro', 'físico', 'orçamentário'), CONTROLES):
            exigir(banco.execute(consulta).fetchone() == esperado, f'Controle {nome} divergente.')


def copiar(origem, saida, limite):
    digest = hashlib.sha256()
    total = 0
    while dados := origem.read(1024 * 1024):
        total += len(dados)
        exigir(total <= limite, 'Tamanho acima do limite.')
        saida.write(dados)
        digest.update(dados)
    return total, digest.hexdigest()


def abrir(arquivo):
    resposta = http.urlopen(RELEASE + arquivo, timeout=60)
    destino = url.urlsplit(resposta.geturl())
    exigir(destino.scheme == 'https' and destino.hostname in {
        'github.com', 'release-assets.githubusercontent.com', 'objects.githubusercontent.com'
    }, 'Destino de distribuição inesperado.')
    return resposta


def distribuicao():
    fixado = os.environ.get('MANIFESTO_SHA256', '')
    exigir(re.fullmatch(r'[0-9a-f]{64}', fixado), 'SHA-256 do manifesto obrigatório.')
    with abrir('PUBLICO.json') as origem:
        raw = origem.read(65537)
    exigir(len(raw) <= 65536 and hashlib.sha256(raw).hexdigest() == fixado, 'Manifesto divergente.')
    dados = json.loads(raw)
    nome = 'consulta-publica.sqlite.gz'
    exigir(dados['version'] == VERSAO and dados['url'] == RELEASE + nome, 'Versão ou URL divergente.')
    with tempfile.TemporaryDirectory() as pasta:
        gz, db = (Path(pasta) / n for n in ('origem.gz', 'consulta.sqlite'))
        with abrir(nome) as origem, gz.open('xb') as saida:
            identidade = copiar(origem, saida, 100*1024*1024)
        exigir(identidade == (dados['gzip_bytes'], dados['gzip_sha256']), 'Gzip divergente.')
        with gzip.open(gz, 'rb') as origem, db.open('xb') as saida:
            identidade = copiar(origem, saida, 150*1024*1024)
        exigir(identidade == (dados['snapshot_bytes'], dados['snapshot_sha256']), 'SQLite divergente.')
        conferir_banco(db)
    log('Download anônimo em diretório vazio, manifesto e dois hashes conferidos. '
        'SQLite íntegro. Controles reproduzidos para 476 notas, 221 intervenções e 321 dotações.')


def normal(texto):
    return ''.join(c for c in unicodedata.normalize('NFD', texto).lower() if not unicodedata.combining(c))


def endereco_app():
    base = os.environ.get('APP_URL', PRODUCAO).rstrip('/') + '/'
    exigir(re.fullmatch(r'https://[a-z0-9][a-z0-9-]*\.streamlit\.app/', base), 'URL inválida para o aplicativo.')
    return base


def contexto(k):
    return 'GI:187' if k in ('institucional', 'financeira', 'juridica') else 'ACERVO'


def app_url(base, k):
    parametros = dict(trajetoria=k, contrato=contexto(k), nivel='fichas')
    if k == 'orcamentaria':
        parametros['ano'] = '2026'
    return base + '?' + url.urlencode(parametros)


def carregar(pagina, endereco):
    resp = pagina.goto(endereco, wait_until='domcontentloaded', timeout=90000)
    exigir(resp is not None and resp.status < 400, 'Falha HTTP na página.')


def aguardar(pagina, obter, mensagem, segundos=70):
    fim = time.monotonic() + segundos
    while time.monotonic() < fim:
        for quadro in pagina.frames:
            if not quadro.is_detached():
                from playwright.sync_api import Error
                try:
                    encontrado = obter(quadro)
                except Error:
                    continue
                if encontrado:
                    return encontrado
        pagina.wait_for_timeout(400)
    raise Falha(mensagem)


def app_render(pagina, k):
    def tela(q):
        campo = q.get_by_role('textbox', name='Buscar nos registros')
        return q if campo.count() and campo.first.is_visible() else None
    quadro = aguardar(pagina, tela, 'Interface com filtros não carregou.')
    quadro.locator('.panel.results tbody tr').first.wait_for(state='visible', timeout=35000)
    for tab, titulo in [('Linha do tempo', 'Linha do tempo documental'),
                        ('Matriz de relacionamentos', 'Matriz de relacionamentos')]:
        quadro.get_by_role('tab', name=tab, exact=True).click(timeout=15000)
        quadro.get_by_role('heading', name=titulo, exact=True).wait_for(state='visible', timeout=15000)
    quadro.get_by_role('tab', name='Registros', exact=True).click()
    if k in ('financeira','orcamentaria','fisica'):
        detalhes = quadro.locator('details').filter(has_text='Consulta ao SQLite').first
        detalhes.locator('summary').click(timeout=10000)
        marcadores = {
            'financeira': ['476', '555.205.746,39'],
            'orcamentaria': ['321', '2.393.369.118,98'],
            'fisica': ['221', '46'],
        }
        texto = detalhes.inner_text(timeout=10000)
        exigir(all(v in texto for v in marcadores[k]), 'Indicadores exibidos divergem do controle.')


def links(q):
    return q.locator('a[href], iframe[src]').evaluate_all(
        '(els) => els.map(e => ({url:e.href || e.src, texto:e.innerText || e.title || ""}))')


def limpo(raw):
    p = url.urlsplit(raw)
    if p.hostname == 'www.google.com' and p.path == '/url':
        args = url.parse_qs(p.query)
        return (args.get('q') or args.get('url') or [''])[0]
    return raw


def link_portal(q, k):
    for item in links(q):
        alvo = url.urljoin(PORTAL, limpo(item['url']))
        p = url.urlsplit(alvo)
        slug = normal(url.unquote(p.path).rstrip('/').rsplit('/', 1)[-1])
        if alvo.startswith(PORTAL) and (k in slug or (k == 'juridica' and 'processual' in slug)):
            return alvo


def link_relatorio(q):
    for item in links(q):
        endereco = limpo(item['url'])
        p = url.urlsplit(endereco)
        if (p.scheme == 'https' and p.hostname in {'datastudio.google.com', 'lookerstudio.google.com'}
                and re.match(r'^/(?:embed/)?reporting/[a-zA-Z0-9-]+(?:/|$)', p.path)):
            return endereco


def botao_investigar(q, k):
    for item in links(q):
        endereco = limpo(item['url'])
        p = url.urlsplit(endereco)
        args = url.parse_qs(p.query)
        if (endereco.startswith(PRODUCAO) and args.get('trajetoria') == [k]
                and args.get('contrato') == [contexto(k)] and args.get('nivel') == ['fichas']
                and (k != 'orcamentaria' or args.get('ano') == ['2026'])):
            return endereco


def portal_e_relatorios(pagina, k, relatorios):
    carregar(pagina, PORTAL + 'in%C3%ADcio')
    destino = aguardar(pagina, lambda q: link_portal(q, k), 'Trajetória ausente no portal.', 20)
    carregar(pagina, destino)
    relatorio = aguardar(pagina, link_relatorio, 'Referência ao relatório ausente no portal.', 25)
    if not relatorios:
        return
    carregar(pagina, relatorio)
    alvo = aguardar(pagina, lambda q: botao_investigar(q, k), 'Relatório sem ligação pública Investigar resolvida.', 40)
    carregar(pagina, alvo)
    app_render(pagina, k)


def navegacao(testar_app, testar_portal, testar_relatorios):
    from playwright.sync_api import sync_playwright
    falhas = []
    with sync_playwright() as pw, pw.chromium.launch(channel='chrome', headless=True) as navegador:
        for k in ROTAS:
            for nome, ligado in [('Aplicativo', testar_app), ('Portal e relatórios' if testar_relatorios else 'Portal', testar_portal or testar_relatorios)]:
                if not ligado:
                    continue
                ctx = navegador.new_context(locale='pt-BR', viewport={'width':1360,'height':900})
                try:
                    pagina = ctx.new_page()
                    if nome == 'Aplicativo':
                        carregar(pagina, app_url(endereco_app(), k))
                        app_render(pagina, k)
                    else:
                        portal_e_relatorios(pagina, k, testar_relatorios)
                    log(f'{nome} · {ROTAS[k]} · verificado em sessão nova.')
                except Exception as exc:
                    erro = str(exc) if isinstance(exc, Falha) else type(exc).__name__
                    log(f'{nome} · {ROTAS[k]} · falhou ({erro}).')
                    falhas.append(k)
                finally:
                    ctx.close()
    exigir(not falhas, 'Há superfícies pendentes de verificação.')


if __name__ == '__main__':
    ativo = lambda nome: os.getenv(nome, 'false').lower() == 'true'
    try:
        if ativo('SQLITE'):
            distribuicao()
        if any(ativo(k) for k in ['APP','PORTAL','RELATORIOS']):
            navegacao(ativo('APP'), ativo('PORTAL'), ativo('RELATORIOS'))
        else:
            exigir(ativo('SQLITE'), 'Selecione ao menos uma verificação.')
    except Exception as exc:
        log(str(exc) if isinstance(exc, Falha) else f'Falha na verificação ({type(exc).__name__}).')
        raise SystemExit(1) from None
