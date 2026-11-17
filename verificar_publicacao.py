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


def quadro_dados(pagina):
    def tela(q):
        campo = q.get_by_role('textbox', name='Buscar nos registros')
        return q if campo.count() and campo.first.is_visible() else None
    return aguardar(pagina, tela, 'Interface com filtros não carregou.')


def app_render(pagina, k, inicio=None):
    quadro = quadro_dados(pagina)
    quadro.locator('.panel.results tbody tr').first.wait_for(state='visible', timeout=35000)
    if inicio is not None:
        log(f'{ROTAS[k]} · da abertura da URL à primeira linha de dados visível: {time.monotonic()-inicio:.2f} s (navegador e rede).')
    for tab, titulo in [('Linha do tempo', 'Linha do tempo documental'),
                        ('Matriz de relacionamentos', 'Matriz de relacionamentos')]:
        quadro.get_by_role('tab', name=tab, exact=True).click(timeout=15000)
        quadro.get_by_role('heading', name=titulo, exact=True).wait_for(state='visible', timeout=15000)
    quadro.get_by_role('tab', name='Registros', exact=True).click()
    if k == 'fisica':
        quadro.get_by_role('heading', name='Situação de cada intervenção').wait_for(state='visible')
        cartao = quadro.locator('.numcard').filter(has_text='Intervenções distintas')
        exigir(cartao.locator('strong').inner_text() == '221', 'Quantidade de intervenções divergente.')
    if k in ('financeira','orcamentaria'):
        detalhes = quadro.locator('details').filter(has_text='Consulta ao SQLite').first
        detalhes.locator('summary').click(timeout=10000)
        marcadores = {
            'financeira': ['476', '555.205.746,39'],
            'orcamentaria': ['321', '2.393.369.118,98'],
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
                and re.match(r'^/(?:u/\d+/)?(?:embed/)?reporting/[a-zA-Z0-9-]+(?:/|$)', p.path)):
            return endereco


def destino_investigar(endereco, k):
    args = url.parse_qs(url.urlsplit(endereco).query)
    return (endereco.startswith(PRODUCAO) and args.get('trajetoria') == [k]
            and args.get('contrato') == [contexto(k)] and args.get('nivel') == ['fichas']
            and (k != 'orcamentaria' or args.get('ano') == ['2026']))


def botao_investigar(q, k):
    for item in q.locator('a[href]').all():
        if item.is_visible() and destino_investigar(limpo(item.get_attribute('href') or ''), k):
            return item
    rotulo = q.get_by_text(re.compile(r'^Investigar(?:\s|$)', re.I))
    for candidato in rotulo.all():
        if candidato.is_visible():
            return candidato


def validar_inicio(pagina):
    carregar(pagina, PORTAL + 'in%C3%ADcio')
    for elemento in pagina.locator('iframe').all():
        if elemento.is_visible():
            elemento.scroll_into_view_if_needed(timeout=5000)

    def encontrar(quadro):
        if quadro == pagina.main_frame or not quadro.url.startswith(PRODUCAO):
            return False
        titulo = quadro.locator('.hero h2')
        if not titulo.count() or not titulo.first.is_visible():
            return False
        if '028/2012' not in titulo.first.inner_text() or not quadro.get_by_text('GI:187', exact=True).count():
            return False
        urls = quadro.locator('a.trajcard').evaluate_all('(els) => els.filter(e => e.getClientRects().length).map(e => e.href)')
        rotas = set()
        for endereco in urls:
            args = url.parse_qs(url.urlsplit(endereco).query)
            if endereco.startswith(PRODUCAO) and args.get('contrato') == ['GI:187']:
                rotas.update(args.get('trajetoria', []))
        return rotas == set(ROTAS)

    aguardar(pagina, encontrar, 'O aplicativo incorporado não exibiu o contrato-piloto e os seis cartões.', 55)


ROTULOS = {
    'institucional': ('tipo', r'intervenção'), 'financeira': ('ano_origem', r'^20[12]\d$'),
    'orcamentaria': ('Exercício', r'^20[12]\d$'), 'juridica': ('tipo', r'instrumento aditivo'),
    'territorial': ('qualificacao', r'atribuição territorial|localização comprovada'),
    'fisica': ('obra', r'em andamento'),
}


LINHAS_RELATORIOS = {
    'financeira': {'2026': ('117', '98.270.629,22', '98.270.629,22')},
    'orcamentaria': {'2026': ('321', '2.393.369.118,98')},
    'territorial': {
        'Atribuição territorial estimada': ('1518',), 'Localização comprovada': ('660',),
        'Vínculo candidato': ('20',),
    },
    'fisica': {'E03 - EM ANDAMENTO': ('62',), 'E04 - CONTRATADA E NÃO INICIADA': ('60',),
               'E01 - CONCLUÍDA': ('21',)},
}


def valor_celula(texto):
    return ' '.join(texto.replace('R$', '').replace('.', '').split()).casefold()


def dados_relatorio(quadro, k):
    if url.urlsplit(quadro.url).hostname not in {'datastudio.google.com','lookerstudio.google.com'}:
        return False
    rotulo, dado = ROTULOS[k]
    cabecalho = quadro.get_by_text(rotulo, exact=True)
    celulas = quadro.locator('.row .cell-value').filter(has_text=re.compile(dado, re.I))
    if not (cabecalho.count() and cabecalho.first.is_visible() and celulas.count() and celulas.first.is_visible()):
        return False
    if k not in LINHAS_RELATORIOS:
        return True
    linhas = quadro.locator('.row').evaluate_all('''rows => rows.filter(row => !row.querySelector('.row')).map(row =>
        Array.from(row.querySelectorAll('.cell-value'), el => el.innerText || '')).filter(v => v.length)''')
    disponiveis = [[valor_celula(v) for v in linha] for linha in linhas]
    for rotulo, esperados in LINHAS_RELATORIOS[k].items():
        linha = next((row.copy() for row in disponiveis if valor_celula(rotulo) in row), None)
        if linha is None:
            return False
        for valor in map(valor_celula, esperados):
            if valor not in linha:
                return False
            linha.remove(valor)
    return True


def portal_e_relatorios(pagina, k, relatorios):
    carregar(pagina, PORTAL + 'in%C3%ADcio')
    destino = aguardar(pagina, lambda q: link_portal(q, k), 'Trajetória ausente no portal.', 20)
    carregar(pagina, destino)
    relatorio = aguardar(pagina, link_relatorio, 'Referência ao relatório ausente no portal.', 25)
    if not relatorios:
        return
    for elemento in pagina.locator('iframe').all():
        if elemento.is_visible():
            elemento.scroll_into_view_if_needed(timeout=5000)
    aguardar(pagina, lambda q: dados_relatorio(q, k), 'Tabela incorporada sem cabeçalho e dados verificáveis.', 50)
    log(f'Relatório · {ROTAS[k]} · cabeçalho e células de dados conferidos no iframe do portal.')
    if k in LINHAS_RELATORIOS:
        log(f'Relatório · {ROTAS[k]} · valores de referência comparados por linha no iframe.')
    direto = url.urlsplit(relatorio)
    carregar(pagina, direto._replace(path=direto.path.replace('/embed/reporting/', '/reporting/')).geturl())
    aguardar(pagina, lambda q: dados_relatorio(q, k), 'Dados ausentes no relatório aberto diretamente.', 40)
    log(f'Relatório · {ROTAS[k]} · cabeçalho e células de dados conferidos na abertura direta sem conta.')
    botao = aguardar(pagina, lambda q: botao_investigar(q, k), 'Botão Investigar ausente no relatório público.', 40)
    botao.click(timeout=10000)
    fim = time.monotonic() + 30
    while time.monotonic() < fim:
        for aba in pagina.context.pages:
            atual = url.urlsplit(aba.url)
            if atual.hostname == 'www.google.com' and atual.path == '/url' and destino_investigar(limpo(aba.url), k):
                for link in aba.get_by_role('link').all():
                    href = link.get_attribute('href') or ''
                    if destino_investigar(href, k) and link.is_visible():
                        link.click(timeout=10000)
                        log(f'Investigar · {ROTAS[k]} · seguido o link para o contexto correto no aviso de redirecionamento do Google.')
                        break
            if destino_investigar(aba.url, k):
                app_render(aba, k)
                return
        pagina.wait_for_timeout(350)
    raise Falha('O botão Investigar não abriu o contexto de referência.')


def conferir_recorte(pagina, ano, notas, montante):
    quadro = quadro_dados(pagina)
    detalhes = quadro.locator('details').filter(has_text='Consulta ao SQLite').first
    if detalhes.get_attribute('open') is None:
        detalhes.locator('summary').click(timeout=10000)
    item = detalhes.locator('.figures > div').filter(has=quadro.get_by_text('Notas', exact=True))
    exigir(item.locator('strong').inner_text(timeout=16000) == notas, 'Contagem alterada entre sessões.')
    exigir(montante in detalhes.inner_text(), 'Montante alterado entre sessões.')
    exigir(ano in detalhes.locator('p').inner_text(), 'Exercício discrepante no recorte.')
    return quadro


def sessoes_e_ficha(navegador):
    ctx_a, ctx_b = (navegador.new_context(locale='pt-BR') for _ in range(2))
    try:
        a, b = ctx_a.new_page(), ctx_b.new_page()
        base = app_url(endereco_app(), 'financeira')
        # O segundo navegador inicia enquanto o primeiro ainda renderiza o componente.
        a.goto(base + '&ano=2012', wait_until='commit')
        b.goto(base + '&ano=2026', wait_until='commit')
        conferir_recorte(a, '2012', '3', '6.426.809,42')
        conferir_recorte(b, '2026', '117', '98.270.629,22')
        log('Sessões simultâneas · 2012 e 2026 renderizaram as contagens e os montantes esperados no primeiro acesso.')
        ficha = app_url(endereco_app(), 'juridica').replace('nivel=fichas','nivel=origem') + '&evento=GI%3A187'
        carregar(a, ficha)
        q = quadro_dados(a)
        dialogo = q.get_by_role('dialog')
        dialogo.get_by_role('heading', name='Ficha de evidência').wait_for(state='visible')
        dialogo.get_by_role('heading', name='Origem da informação').wait_for(state='visible')
        exigir('GI:187' in dialogo.locator('.idline').inner_text(), 'Identidade da ficha divergente.')
        log('URL direta · ficha jurídica aberta com a origem documental e o identificador do piloto.')
        a.go_back(wait_until='domcontentloaded', timeout=60000)
        quadro = conferir_recorte(a, '2012', '3', '6.426.809,42')
        log('URL direta da ficha jurídica GI:187 abriu com a origem. Voltar restaurou 2012 e os respectivos valores.')
        campo = quadro.get_by_role('textbox', name='Buscar nos registros')
        campo.fill('ZZZ-SMARTHOUSE-TESTE-SEM-OCORRENCIAS')
        quadro.locator('.panel.results').get_by_text('Nenhum registro neste recorte', exact=True).wait_for(state='visible')
        exigir(not quadro.locator('.panel.results tbody tr').count(), 'A seleção vazia exibiu linhas.')
        conferir_recorte(b, '2026', '117', '98.270.629,22')
        quadro.get_by_role('button', name='Limpar filtros').click()
        quadro.locator('.panel.results tbody tr').first.wait_for(state='visible')
        exigir(campo.input_value() == '', 'A busca não foi limpa.')
        conferir_recorte(b, '2026', '117', '98.270.629,22')
        log('Duas sessões anônimas simultâneas preservaram os recortes de 2012 (3 notas) e 2026 (117 notas). A busca vazia indicou ausência e voltou a exibir linhas após limpar.')
    finally:
        ctx_a.close()
        ctx_b.close()


def navegacao(testar_app, testar_portal, testar_relatorios):
    from playwright.sync_api import sync_playwright
    falhas = []
    selecionada = os.getenv('TRAJETORIA', 'todas') or 'todas'
    exigir(selecionada == 'todas' or selecionada in ROTAS, 'Trajetória desconhecida.')
    trilhas = ROTAS if selecionada == 'todas' else [selecionada]
    with sync_playwright() as pw, pw.chromium.launch(channel='chrome', headless=True) as navegador:
        if testar_app and selecionada == 'todas':
            try:
                sessoes_e_ficha(navegador)
            except Exception as exc:
                erro = str(exc) if isinstance(exc, Falha) else type(exc).__name__
                log(f'Sessões concorrentes, URL direta, Voltar e busca vazia · falhou ({erro}).')
                falhas.append('sessoes')
        if (testar_portal or testar_relatorios) and selecionada == 'todas':
            ctx = navegador.new_context(locale='pt-BR', viewport={'width':1360,'height':900})
            try:
                validar_inicio(ctx.new_page())
                log('Portal · início · o iframe exibiu SEHAB 028/2012 (GI:187) e os seis cartões com links de trajetória.')
            except Exception as exc:
                erro = str(exc) if isinstance(exc, Falha) else type(exc).__name__
                log(f'Portal · início · falhou ({erro}).')
                falhas.append('inicio')
            finally:
                ctx.close()
        for k in trilhas:
            for nome, ligado in [('Aplicativo', testar_app), ('Portal e relatórios' if testar_relatorios else 'Portal', testar_portal or testar_relatorios)]:
                if not ligado:
                    continue
                ctx = navegador.new_context(locale='pt-BR', viewport={'width':1360,'height':900})
                try:
                    pagina = ctx.new_page()
                    if nome == 'Aplicativo':
                        endereco = app_url(endereco_app(), k)
                        inicio = time.monotonic()
                        carregar(pagina, endereco)
                        app_render(pagina, k, inicio)
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
