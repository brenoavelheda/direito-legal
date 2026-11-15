# direito-legal

Plugin do [Claude Code](https://claude.com/claude-code) para consultas de direito brasileiro. Ele responde com cada afirmação citada e verificada numa base local de fontes oficiais: leis capturadas do Planalto e precedentes de sites `*.jus.br`.

## O que vem no plugin

| Parte | Função |
|---|---|
| `/direito-legal:consulta` | Responde à pergunta num formato fixo: resposta, fundamentos com tag de fonte, certeza, o que mudaria a resposta, próximos passos, gatilho objetivo de advogado e contraditor. |
| `/direito-legal:pesquisar` | Cria ou amplia uma categoria da base (guia, normas, precedentes, fontes, perguntas) a partir de fontes oficiais. |
| `/direito-legal:configurar` | Cria o `perfil.md` e as pastas `casos/` do usuário. |
| agente `contraditor` | Faz o papel da parte contrária e tenta derrubar a resposta. |
| servidor MCP `base-juridica` (Python) | Captura leis e precedentes, mantém o índice de busca (SQLite FTS5) e verifica citações: artigo, inciso, parágrafo, súmula, tema e acórdão. |

As regras de conduta estão em [`plugin/regras.md`](plugin/regras.md) e as tags de fonte em [`plugin/marcadores.md`](plugin/marcadores.md).

## Requisitos

- Claude Code;
- [uv](https://docs.astral.sh/uv/), que instala o Python 3.12 e as dependências do servidor na primeira execução.

## Instalação

```bash
git clone https://github.com/brenoavelheda/direito-legal
claude plugin marketplace add ./direito-legal
claude plugin install direito-legal@direito-legal
```

## Pasta de dados

Os dados do usuário nunca ficam neste repositório. Eles ficam numa pasta própria:

| Caminho | Conteúdo |
|---|---|
| `base/` | Leis, precedentes, categorias e `historico-normativo.md`. Só o servidor grava aqui. |
| `perfil.md` | Quem é o usuário: domicílio, profissão, assuntos atuais. |
| `casos/<assunto>/` | Fatos, cronologia, histórico de consultas e documentos de cada assunto. |
| `avaliacao/` | Perguntas e resultados das avaliações. |

A pasta é definida pela variável de ambiente `DIREITO_LEGAL_DADOS`, que deve apontar para uma pasta que já existe. Sem a variável, o plugin usa `~/direito-legal-dados`. Para definir a variável no Claude Code, use o `settings.json`:

```json
{ "env": { "DIREITO_LEGAL_DADOS": "C:/caminho/para/meus-dados-juridicos" } }
```

Para ter histórico das alterações, transforme a pasta de dados num repositório git privado.

## Primeiro uso

1. Rode `/direito-legal:configurar` para criar o perfil e os casos.
2. Baixe o acervo inicial, as 12 leis do catálogo (CF, CC, CPC, CDC, Lei do Inquilinato…):

   ```bash
   cd direito-legal/plugin/servidor
   uv run python -m base_juridica.cli baixar-acervo
   ```

3. Pergunte com `/direito-legal:consulta <sua pergunta>`. Leis e precedentes que faltarem são baixados e registrados durante a consulta.

## Limites

- O plugin redige, mas nada é enviado nem protocolado. Peticionar exige advogado, salvo nas exceções listadas em `regras.md` (JEC até 20 salários mínimos, JEF, Justiça do Trabalho, habeas corpus, processo administrativo).
- Prazos são sempre estimados, com contagem conservadora e a marca `[verificar]`.
- A existência de acórdãos avulsos (REsp, RE…) não é verificada. Eles só passam na verificação com a URL oficial ou com a marca `[conhecimento do modelo — verificar]`.
- O leitor de páginas do Planalto depende do HTML do site, que pode mudar.

## Testes e avaliação

```bash
cd plugin/servidor
uv run pytest                                  # servidor
uv run pytest ../../evals                      # avaliação (unitários)
uv run python ../../evals/rodar.py --limite 5  # questões da OAB pela skill consulta (usa o claude -p; tem custo)
```

As questões ficam em `evals/oab/questoes.jsonl`: 1ª fase da OAB/FGV, com gabarito oficial. O relatório vai para `<pasta de dados>/avaliacao/resultados/`.

## Licença

Apache License 2.0. Este projeto é obra derivada de [anthropics/claude-for-legal](https://github.com/anthropics/claude-for-legal); veja [`NOTICE`](NOTICE).
