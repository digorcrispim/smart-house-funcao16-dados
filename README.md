# Smart House · consulta pública da Função 16

O Smart House organiza a política habitacional da Prefeitura de São Paulo em seis trajetórias. Selecione o contrato na barra de contexto e abra a trajetória que responde à sua pergunta.

[Abrir a aplicação](https://smart-house-funcao16-pmsp.streamlit.app/) · [Portal institucional](https://sites.google.com/view/smart-house-funcao16-pmsp/in%C3%ADcio) · [Edição dos dados e manifesto](https://github.com/digorcrispim/smart-house-funcao16-dados/releases/tag/v2026.11.16.3)

| Trajetória | Pergunta |
| --- | --- |
| Institucional | Quais órgãos, programas e instrumentos aparecem no registro? |
| Financeira | Que notas comprovam o pagamento e em qual exercício houve desembolso? |
| Orçamentária | Em qual dotação, fonte, classificação e posição o valor foi registrado? |
| Processual / jurídica | Que processo, documento ou instrumento sustenta a relação? |
| Territorial | Qual é o alcance da localização e que evidência sustenta a atribuição? |
| Física | Em que estágio está cada intervenção e há registro de recebimento ou entrega? |

O contrato-piloto é o SEHAB 028/2012. Na financeira, as 476 notas totalizam R$ 555.205.746,39. Na física, o recorte da carteira histórica URB reúne 221 intervenções. No orçamento de 2026, o valor pago de R$ 2.393.369.118,98 se refere às 321 dotações com extração em 27/10/2026 e corte nominal em 31/10/2026. Cada indicador acompanha seu recorte de origem.

## Operação da distribuição

Edição v2026.11.16.3 · esquema 1 · valores na tabela de fatos em centavos de reais.

## Qual arquivo usar

| Arquivo | Bytes | SHA-256 |
|---|---:|---|
| V7 integral, referência histórica | 751.185.920 | `0579ab32559645928fc7b8da27a3a07e4f57a46f6bc8987cf7511b16187aa96f` |
| Projeção anterior, edição privada 2026-11-16.2 | 65.798.144 | `4c7afcadf7bdf434dc3691635c78f7c67f22458b29fc89d28d36800ced0f0e71` |
| Projeção pública SQLite | 61.874.176 | `d9f8fc7718f7dc2403eba219f126684c066b50bad48c20bcce895af69e23b1e5` |
| Distribuição compactada da projeção pública | 29.805.203 | `1c2479bf9f5f3467c1d46ac9f4d691905013310acc7f87acb68ba7622a9e1891` |

A aplicação recebe o manifesto `PUBLICO.json` junto ao código. O hash desse manifesto é `bf5008688e6a046b551779022623f12f78e800e6933437062a13342056caae05`. O endereço fixado é o arquivo `consulta-publica.sqlite.gz` da distribuição `v2026.11.16.3` em `digorcrispim/smart-house-funcao16-dados`. Um endereço de visualização do Drive exige outro fluxo e não faz parte desse carregamento.

## Como ocorre a recuperação

1. Ao iniciar, o aplicativo chama `public_bootstrap.prepare_database()`. O instalador lê o manifesto incluído na versão do código e procura a cópia local no diretório do SHA-256 aprovado.
2. Se encontrar a cópia, verifica tamanho, hash, `PRAGMA quick_check`, versão de esquema, contagens de cada tabela, controles do piloto, carteira URB e fotografia orçamentária. O processo reutiliza a validação enquanto a identidade, as datas do sistema de arquivos e o tamanho permanecerem iguais.
3. Na ausência de cópia válida, uma trava do sistema operacional limita a preparação a um processo por vez. O download HTTPS usa blocos de 256 KiB e emite a contagem de bytes pelo callback de progresso. A conexão tem timeout de 15 s e prazo de 150 s por tentativa. O instalador faz até três tentativas. Cada tentativa começa com um arquivo temporário vazio.
4. O instalador confere tamanho e SHA-256 do pacote. A descompactação escreve um único arquivo temporário gerado pelo servidor e impõe o tamanho máximo do manifesto. Após a validação do banco, sincroniza o arquivo e usa troca atômica no mesmo sistema de arquivos.
5. A consulta abre o banco em modo somente leitura. Enquanto a cópia permanecer íntegra, filtros, sessões e reinícios do processo reutilizam o arquivo. Se a hospedagem perder o disco, a sequência volta ao download. Nenhum visitante precisa fornecer credencial, URL, arquivo ou caminho local.
6. Se a origem estiver indisponível e o disco estiver vazio, o aplicativo informa a indisponibilidade e permite nova tentativa. Quando um futuro manifesto aceitar uma versão pública anterior, a chave `fallbacks` deve conter sua especificação completa. O instalador só usa uma cópia anterior que ainda exista e passe pelo respectivo manifesto. A interface pode informar a edição efetiva com `version_for(path)`. A primeira implantação pública não seleciona a cópia privada como contingência.

## Atualizar os dados

A recuperação repõe a mesma edição. Uma atualização requer uma decisão explícita de versão.

1. Recupere a fonte homologada no ambiente administrativo e confira seu recibo. Gere outra cópia derivada com versão e arquivo próprios. Preserve a edição pública anterior e seus hashes.
2. Inspecione todos os campos, chaves e registros comprimidos. Revise dados pessoais desnecessários, anotações livres e permissões das referências. Guarde o inventário de origem e a comparação de chaves. A edição atual preserva as nove tabelas e os campos financeiros estruturados da projeção anterior.
3. Registre a extração, o corte nominal e os universos de cada fonte. Repita os controles com os resultados esperados daquele corte. Na edição atual, a extração SEPLAN de 27/10/2026 às 03:24:54 alimenta a fotografia com fim nominal em 31/10/2026 às 23:59:59.
4. Gere o arquivo GZIP com nome de membro vazio e data interna zero. Calcule ambos os tamanhos e hashes. Crie uma nova release usando um identificador próprio e envie o arquivo de distribuição e o manifesto homologado. Mantenha o banco fora do histórico Git. Não substitua o binário de uma versão existente.
5. Confira o download público, o hash e o arranque da aplicação candidata com armazenamento vazio. Conserve separadamente resultados de testes locais e de testes na hospedagem.
6. Fixe o novo manifesto no commit da aplicação e implante a candidata homologada. Registre release, commit, cobertura e testes no recibo. Se o esquema mudar, publique o código compatível na mesma troca.

## Reverter uma atualização

Volte ao commit público homologado anterior e a seu manifesto. Preserve o artefato versionado que esse manifesto referencia. Se a cópia local da edição anterior ainda existir, ela será validada e reutilizada. Com armazenamento vazio, o instalador fará novo download. Teste uma trajetória de cada vez, usando o piloto, a carteira URB e o corte orçamentário daquela edição. Se a operação exigir voltar à implantação privada, restaure primeiro suas permissões privadas e só então reative o código antigo. Os dados da edição privada não integram a lista automática de contingência pública.

## Evidências desta edição

Na preparação local passaram 66 controles SQL herdados, 16 comparações entre as cópias e 17 controles operacionais. Os ensaios usaram o arquivo de distribuição real em um servidor HTTPS de loopback isolado. Em quatro processos simultâneos e com diretório vazio houve um único download. O teste também interrompeu uma resposta, adulterou o digest recebido, simulou erro HTTP 503, alterou o arquivo local, testou o limite de extração, rejeitou esquema divergente e restaurou uma versão pública homologada em um cenário de atualização.

O teste frio local levou 0,427 s. A mediana de 40 consultas ao piloto foi de 0,103 ms. Essas medições descrevem o ambiente local. Os controles não medem a latência da internet nem a disponibilidade do Streamlit Community Cloud.

`FONTES_DOCUMENTAIS.csv` registra as referências com leitura não comprovada e os endereços externos conservados. Foram observados 88 arquivos Drive com acesso restrito e seis sem permissão pública confirmada. A edição conserva identificação documental, seções e relações e retira os endereços de consulta privada. Uma URL externa registrada pode depender da disponibilidade de seu publicador.


## Verificação no serviço

O Streamlit registrou a recuperação e validação da edição de 61.874.176 bytes em 1,307 s após reinício. O tempo se refere ao banco. O navegador também aguarda a aplicação e a renderização das páginas.

[Download e controles SQL em sessão anônima](https://github.com/digorcrispim/smart-house-funcao16-dados/actions/runs/44003394302) · [Navegação nas seis trajetórias](https://github.com/digorcrispim/smart-house-funcao16-dados/actions/runs/44004282361) · [Portal](https://github.com/digorcrispim/smart-house-funcao16-dados/actions/runs/44004508042)
