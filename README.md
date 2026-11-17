# Smart House · Função 16

Consulta pública em https://smart-house-funcao16-pmsp.streamlit.app/

A edição **v2026.11.17.1** acrescenta Urbanização à aplicação existente, preservando seis trajetórias independentes e os dados anteriores. Acesse Modalidades da Política Habitacional → Urbanização.

- Carteira histórica: 221 IDs; consolidada GI 2608: 176 entregas / 174 IDs.
- Custos gerenciais por área e entrega, com PØ, PN, INCC, valores literais e localizadores.
- Execução SOF no grão nativo da nota, sem distribuir pagamentos por sub-ID.
- Cenários territoriais V4.6 A/B/piso/teto preservados como estimativas.
- Caderno de análise local ao navegador, com exportação de registros e contexto.

## Distribuição atual

[Release e manifesto](https://github.com/digorcrispim/smart-house-funcao16-dados/releases/tag/v2026.11.17.1)

| Artefato | Bytes | SHA-256 |
|---|---:|---|
| SQLite, esquema 2 | 72.998.912 | 54cc0ab033cdc975ecbd8150391d7a3d37e32b01263e37be225524f08645052d |
| GZIP | 30.254.257 | aa0b65420d83dc04f0050d6d793001590590b85ba623917892a1d874e867b255 |
| PUBLICO.json | 6.193 | e4d35e3b09b5a95f4830ad530677fb810544c7c34ce4ba9aac4eb2736c1dd793 |

O inicializador confere hash, tamanho, esquema, contagens e controles antes de abrir SQLite somente para leitura. A release anterior v2026.11.16.3 permanece disponível; o V7 integral não foi alterado. As nove tabelas anteriores permanecem idênticas. Oito tabelas foram acrescentadas.

## Controles de continuidade

SEHAB 028/2012: 476 notas; R$ 555.205.746,39 pagos, incluindo restos. SEHAB 037/2012: 169 notas; R$ 330.827.714,40 pagos. Sua diferença V4.6, notas menos cadastro, é −R$ 45.069.065,49 e continua pendente de explicação documental. A atualização monetária GI não representa pagamento.

O workflow manual Verificação pública aceita o hash do manifesto como entrada. Para esta edição use o hash acima, selecione SQLite e aplicativo; mantenha portal e relatórios desmarcados para verificar somente o escopo incremental. O teste usa sessões novas sem credenciais. O histórico preserva as verificações da edição anterior.

Fontes completas e documentos mantêm suas permissões originais. A projeção pública conserva os campos administrativos necessários à consulta e os localizadores. Não implica abertura dos documentos-fonte restritos.
