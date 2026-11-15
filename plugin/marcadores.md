# Marcadores de proveniência

Vocabulário canônico. A tag vai no fim da linha do dado que sustenta a conclusão, nunca no parágrafo inteiro. Na seção `## Fundamentos` da `consulta`, toda linha `- ` termina com uma destas tags.

| Tag | Quando usar |
|---|---|
| `[Planalto]` | Texto de lei obtido do planalto.gov.br **nesta sessão** (`baixar_lei`, `atualizar` ou WebFetch no Planalto). |
| `[STJ]`, `[STF]`, `[TST]`, `[TJSP]`… | Precedente ou página obtida do site oficial do tribunal (*.jus.br) **nesta sessão** e conferida (`baixar_precedente` com `conferido: true`, ou WebFetch na página oficial). |
| `[DataJud]` | Dado de processo obtido do DataJud nesta sessão (v1b). |
| `[base — capturado AAAA-MM-DD]` | Texto lido da base (`ler_artigo`, `buscar`, `ler_categoria`) — a data é o `capturado_em` devolvido pela ferramenta. |
| `[base — capturado AAAA-MM-DD — desatualizado]` | Mesmo caso, quando `ler_artigo` devolveu `desatualizado: true` (recaptura falhou e a cópia tem mais de 30 dias). Baixa a certeza. |
| `[comentário — <site>]` | Blog, artigo, notícia ou qualquer fonte não oficial. Nunca sustenta sozinha uma afirmação de norma. |
| `[conhecimento do modelo — verificar]` | Afirmação que não veio de fonte recuperada nesta sessão nem da base. Também substitui citação reprovada pelo `verificar_citacoes` que não puder ser corrigida. |
| `[verificar]` | Sufixo obrigatório em prazo estimado, em precedente com `conferido: false` e em redação histórica com `incerto: true`. Combina com as outras: `[base — capturado 2026-11-15] [verificar]`. |

Expressão regular usada pela avaliação para reconhecer uma tag:

```
\[(Planalto|STJ|STF|TST|TSE|TNU|TJ[A-Z]{2}|TRF\d|DataJud|base — capturado \d{4}-\d{2}-\d{2}( — desatualizado)?|comentário — [^\]]+|conhecimento do modelo — verificar|verificar)\]
```
