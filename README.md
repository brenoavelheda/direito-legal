# direito-legal

Um consultor de direito brasileiro que roda dentro do [Claude Code](https://claude.com/claude-code). Você pergunta em português comum e recebe uma resposta em que cada afirmação traz a fonte, e em que cada artigo, súmula ou tema citado foi conferido contra o texto oficial: leis do Planalto e precedentes de sites `*.jus.br`.

A base de conhecimento fica no seu computador e cresce com o uso: cada lei baixada e cada assunto pesquisado ficam guardados para as próximas perguntas.

> **Importante:** este plugin ajuda a entender a lei. Ele não é advogado, não substitui advogado em processo e pode errar. Use as respostas como ponto de partida e confira o que for decisivo.

## Sumário

1. [O que é](#o-que-é)
2. [Para que serve](#para-que-serve)
3. [Como funciona](#como-funciona)
4. [Instalação](#instalação)
5. [Primeiro uso](#primeiro-uso)
6. [Atualizar](#atualizar)
7. [Privacidade](#privacidade)
8. [Qualidade e limites](#qualidade-e-limites)
9. [Para quem quer contribuir](#para-quem-quer-contribuir)
10. [Apoie o projeto](#apoie-o-projeto)
11. [Licença e créditos](#licença-e-créditos)

## O que é

O direito-legal é um plugin, isto é, um pacote que acrescenta comandos ao Claude Code. Ele tem três comandos:

| Comando | O que faz |
|---|---|
| `/direito-legal:consulta <pergunta>` | Responde a uma dúvida jurídica num formato fixo, com fonte em cada linha. |
| `/direito-legal:pesquisar <tema>` | Estuda um assunto em fontes oficiais e guarda o resultado na sua base. |
| `/direito-legal:configurar` | Cria o seu perfil e as pastas dos seus assuntos. |

Por trás dos comandos há um pequeno programa local, o servidor `base-juridica`. Ele baixa as leis, guarda tudo em arquivos de texto no seu computador, faz a busca e confere as citações.

## Para que serve

O objetivo é auxiliar na criação de projetos comerciais com consultas jurídicas de fácil acesso, **diminuindo — não eliminando — a necessidade de contratar um profissional apenas para consultas simples à lei**.

### Em projetos e negócios

| Situação | Exemplo de pergunta |
|---|---|
| Viabilidade jurídica de uma ideia | "Quero vender assinatura mensal de um produto pela internet. Que regras de consumo preciso respeitar?" |
| Locação comercial antes de assinar | "O contrato da sala prevê multa de três aluguéis se eu sair antes. Isso é permitido?" |
| CDC numa loja virtual | "Qual é o prazo de arrependimento? Quem paga o frete da devolução? Qual é a garantia legal?" |
| LGPD num app ou site | "Preciso de consentimento para guardar o e-mail dos clientes?" |
| Cobrança ou execução | "Recebi uma citação numa execução. O que pode ser penhorado?" |
| Juizado Especial sem advogado | "Posso entrar sozinho no Juizado contra um fornecedor que não entregou?" |
| Preparar uma consulta paga | "Que perguntas devo levar ao advogado sobre este contrato?" |

### No dia a dia

- **Aluguel:** direito de preferência na compra, multa por sair antes do fim, reparos que cabem ao locador.
- **Consumo:** produto com defeito, troca, devolução de compra feita pela internet.
- **Prazos:** quanto tempo você tem para reclamar ou responder, sempre como estimativa.
- **Dívidas:** prescrição, o que pode e o que não pode ser penhorado.

### O que ele não faz

- **Não substitui advogado em processo.** Quando o caso pede advogado, a resposta diz isso e explica por quê.
- **Não peticiona nem envia nada.** Ele pode ajudar a redigir, mas quem envia e protocola é você.
- **Cobre só legislação federal publicada no Planalto.** Lei estadual e lei municipal ficam de fora.
- **Não dá prazo exato.** Todo prazo é estimado, com contagem conservadora e a marca `[verificar]`. Ele não considera feriados municipais, suspensões por portaria do tribunal nem prazo em dobro.
- **Não consulta o andamento de processos.**

## Como funciona

Uma consulta segue sempre os mesmos passos:

1. **Lê as regras e o seu perfil.** Se a pergunta toca um assunto seu já registrado, lê também os fatos desse caso.
2. **Faz a triagem.** Separa a pergunta em questões jurídicas e confere as premissas. Se você afirmar um prazo ou uma regra que conflita com a base, ele avisa antes de seguir.
3. **Busca na base local.** Procura nos artigos de lei, nos precedentes e nos assuntos já pesquisados. Todo artigo citado é lido no texto oficial.
4. **Preenche o que falta.** Lei que não está na base é baixada do Planalto. Súmula ou tema é registrado a partir da página oficial do tribunal.
5. **Verifica as citações.** Um verificador automático confere cada artigo, inciso, parágrafo, súmula e tema citado. Citação reprovada é corrigida ou sai da resposta.
6. **Chama o contraditor.** Um segundo agente faz o papel da parte contrária e tenta derrubar a resposta.
7. **Entrega no formato fixo** e registra a pergunta na base, para consulta futura.

### As 12 leis do catálogo

Estas leis são reconhecidas pela sigla ou pelo número:

| Lei | Como citar |
|---|---|
| Constituição Federal de 1988 | CF |
| Código Civil (Lei 10.406/2002) | CC |
| Código de Processo Civil (Lei 13.105/2015) | CPC |
| Código de Defesa do Consumidor (Lei 8.078/1990) | CDC |
| Lei de Introdução às Normas do Direito Brasileiro (Decreto-Lei 4.657/1942) | LINDB |
| Lei do Inquilinato (Lei 8.245/1991) | Lei do Inquilinato |
| Alienação fiduciária (Decreto-Lei 911/1969) | Lei da Alienação Fiduciária |
| Cédula de Crédito Bancário (Lei 10.931/2004) | Lei da CCB |
| Bem de família (Lei 8.009/1990) | Lei do bem de família |
| Juizados Especiais (Lei 9.099/1995) | Lei dos Juizados |
| Juizados Especiais Federais (Lei 10.259/2001) | Lei dos JEFs |
| Estatuto da Advocacia e da OAB (Lei 8.906/1994) | Estatuto da OAB |

Qualquer outra lei federal entra na base quando for necessária, desde que tenha página no Planalto. É o caso da LGPD (Lei 13.709/2018), que não está no catálogo e é baixada na primeira pergunta sobre o assunto.

### De onde vêm as fontes

| Tipo de conteúdo | Fonte aceita |
|---|---|
| Texto de lei | `planalto.gov.br` |
| Súmula, súmula vinculante e tema | somente sites `*.jus.br` |
| Outras normas e páginas oficiais | sites `*.gov.br`, `camara.leg.br`, `senado.leg.br`, entre outros |
| Blog, notícia, site de curso | entra só como comentário e nunca sustenta sozinho uma afirmação de norma |

A lista completa de domínios oficiais está em [`fontes.py`](plugin/servidor/src/base_juridica/fontes.py).

### As tags de fonte

Cada linha dos fundamentos termina com uma tag que diz de onde veio a informação:

| Tag | Significado |
|---|---|
| `[Planalto]` | Texto de lei obtido do Planalto nesta conversa. |
| `[STJ]`, `[STF]`, `[TST]`, `[TJSP]`… | Precedente obtido do site oficial do tribunal nesta conversa e conferido. |
| `[base — capturado AAAA-MM-DD]` | Texto lido da sua base local, com a data em que foi baixado. |
| `[base — capturado AAAA-MM-DD — desatualizado]` | A cópia tem mais de 30 dias e a tentativa de atualizar falhou. A certeza cai. |
| `[comentário — <site>]` | Fonte não oficial. |
| `[conhecimento do modelo — verificar]` | Não veio de fonte recuperada nem da base. Confira antes de confiar. |
| `[verificar]` | Vai junto de todo prazo estimado, de precedente que não pôde ser conferido no site oficial e de redação antiga de lei com data incerta. |

A lista completa está em [`plugin/marcadores.md`](plugin/marcadores.md). Ela inclui também `[DataJud]`, reservada para uma versão futura.

Quando um artigo é lido, a cópia da lei com mais de 30 dias é baixada de novo antes de ser usada.

### O formato da resposta

Toda resposta tem as mesmas sete partes, mesmo quando é curta:

| Parte | Conteúdo |
|---|---|
| **Resposta** | A resposta direta, em 1 a 3 frases. |
| **Fundamentos** | Uma afirmação por linha, com a citação e a tag de fonte. |
| **Certeza** | Alta, média ou baixa, com o motivo. |
| **O que mudaria a resposta** | Fatos ou documentos que levariam a outra conclusão. |
| **Próximos passos** | Ações concretas, em ordem. |
| **Advogado** | `não necessário`, ou o gatilho que disparou e o que perguntar numa consulta avulsa. |
| **Contraditor** | `manteve`, `alterou` (com resumo) ou `dispensado`. |

Exemplo ilustrativo, escrito à mão para este README (não é a saída de uma consulta real), para a pergunta "comprei um produto pela internet e me arrependi; posso devolver?":

```
## Resposta
Sim. Em compra feita pela internet, você pode desistir em até 7 dias contados
do recebimento, sem precisar justificar, e a loja devolve o valor pago.

## Fundamentos
- O consumidor pode desistir do contrato em 7 dias, contados da assinatura ou do recebimento do produto, quando a compra é feita fora do estabelecimento comercial — art. 49 do CDC [base — capturado 2026-11-10]
- Os valores pagos durante o prazo de reflexão são devolvidos de imediato, com atualização monetária — art. 49, parágrafo único, do CDC [base — capturado 2026-11-10]
- Compra pela internet é tratada como compra fora do estabelecimento comercial [conhecimento do modelo — verificar]

## Certeza: alta — o texto do artigo é direto e está vigente

## O que mudaria a resposta
- A compra ter sido feita na loja física.
- Terem passado mais de 7 dias desde o recebimento.

## Próximos passos
1. Confira a data do recebimento. O prazo estimado termina 7 dias depois, em contagem conservadora [verificar]
2. Avise a loja por escrito, dentro do prazo, e guarde o comprovante.
3. Se a loja recusar, registre reclamação no Procon.

## Advogado: não necessário

## Contraditor: manteve
```

### Quando ele manda chamar um advogado

A resposta nunca traz um "procure um advogado" genérico. O advogado só aparece quando um destes cinco gatilhos dispara:

| Nº | Gatilho |
|---|---|
| 1 | É preciso peticionar, fora das exceções abaixo. |
| 2 | Ato irreversível de valor alto. |
| 3 | Risco penal. |
| 4 | Prazo processual correndo, com certeza média ou baixa. |
| 5 | A resposta depende de prova ou fato que você não tem. |

Quando um gatilho dispara, a resposta diz qual foi e o que perguntar ao advogado numa consulta avulsa.

Situações em que a lei permite agir sem advogado (exceções ao gatilho 1):

- Juizado Especial Cível, em causas de até 20 salários mínimos, só na 1ª instância (Lei 9.099/95, art. 9º);
- Juizado Especial Federal (Lei 10.259/2001, art. 10);
- Justiça do Trabalho, com os limites da Súmula 425 do TST;
- habeas corpus;
- processos administrativos.

As regras completas estão em [`plugin/regras.md`](plugin/regras.md).

### O contraditor

O contraditor é um segundo agente que recebe a pergunta, os fatos e a resposta proposta. O trabalho dele é derrubar a resposta, não confirmá-la. Ele procura norma em sentido oposto, exceção ignorada, precedente contrário, premissa de fato frágil e erro de prazo.

Ele roda quando a resposta recomenda uma ação, quando o valor é alto ou quando a certeza é média ou baixa. Em pergunta só informativa e de certeza alta, é dispensado.

## Instalação

### Requisitos

Você precisa de três programas. Os comandos abaixo são digitados no terminal: PowerShell no Windows, Terminal no Mac.

| Programa | Para que serve | Windows | Mac |
|---|---|---|---|
| [Claude Code](https://claude.com/claude-code) | É onde o plugin roda. | Siga a instalação oficial. | Siga a instalação oficial. |
| [uv](https://docs.astral.sh/uv/) | Instala o Python (3.12 ou mais novo) e as dependências do servidor sozinho, na primeira execução. | `winget install --id=astral-sh.uv -e` | `brew install uv` |
| [git](https://git-scm.com/) | Baixa o plugin do GitHub. | `winget install --id Git.Git -e` | `xcode-select --install` |

Sem o `winget` ou o `brew`, o uv também pode ser instalado assim:

```powershell
# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

```bash
# Mac
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Depois de instalar, feche e abra o terminal de novo.

### Instalar o plugin

```bash
claude plugin marketplace add brenoavelheda/direito-legal
claude plugin install direito-legal@direito-legal
```

O primeiro comando registra este repositório como fonte de plugins. O segundo instala o plugin. Se o Claude Code já estava aberto, reinicie-o.

## Primeiro uso

Abra o Claude Code e siga esta ordem:

1. **Configure o perfil.**

   ```
   /direito-legal:configurar
   ```

   Ele pergunta o que precisa saber para responder melhor: a sua situação (pessoa física, se tem empresa), a cidade e o estado (definem o foro e os juizados) e os assuntos que você quer acompanhar. Nada disso sai do seu computador.

2. **Faça uma pergunta.**

   ```
   /direito-legal:consulta comprei um produto pela internet e me arrependi. Posso devolver?
   ```

   Não é preciso baixar nada antes. As leis e os precedentes que faltarem são baixados durante a consulta. A primeira execução demora mais, porque o uv instala o Python e as dependências.

3. **Estude um assunto com calma, se quiser.**

   ```
   /direito-legal:pesquisar locação comercial
   ```

   Ele monta uma categoria na base, com guia em linguagem simples, normas, precedentes, fontes e perguntas típicas. As consultas seguintes sobre o assunto ficam mais rápidas e mais completas.

O Claude Code pode pedir a sua permissão para usar as ferramentas do plugin e para acessar a internet. Isso é esperado.

### A pasta de dados

Os seus dados nunca ficam neste repositório. Eles ficam numa pasta própria, que por padrão é `direito-legal-dados` dentro da sua pasta de usuário (`~/direito-legal-dados`). Ela é criada sozinha no primeiro uso.

| Caminho | Conteúdo |
|---|---|
| `base/` | Leis, precedentes, categorias, o índice de busca e o `historico-normativo.md`, que registra as mudanças detectadas nas leis. Só o servidor grava aqui. |
| `perfil.md` | O seu perfil. |
| `casos/<assunto>/` | Fatos, cronologia, histórico de consultas e documentos de cada assunto seu. |
| `avaliacao/` | Perguntas e resultados de avaliações, se você rodar alguma. |

Para usar outra pasta, defina a variável `DIREITO_LEGAL_DADOS` no `settings.json` do Claude Code. No Windows, o arquivo fica em `C:\Users\<seu usuário>\.claude\settings.json`; no Mac, em `~/.claude/settings.json`.

```json
{ "env": { "DIREITO_LEGAL_DADOS": "C:/caminho/para/meus-dados-juridicos" } }
```

A pasta indicada precisa existir antes. Se o caminho estiver errado, o plugin mostra um erro em vez de criar uma base vazia em outro lugar. Reinicie o Claude Code depois de mudar o arquivo.

### Guarde o histórico num repositório privado

Vale transformar a pasta de dados num repositório git **privado**. Assim você tem histórico das alterações e uma cópia de segurança.

Antes, crie na pasta de dados um arquivo `.gitignore` com estas linhas. Elas deixam de fora o índice de busca, que o servidor refaz sozinho, e um arquivo temporário de trava:

```
base/indice.sqlite
base/indice.sqlite-*
base/.trava
```

Depois, no terminal:

```bash
cd ~/direito-legal-dados
git init
git add .
git commit -m "base inicial"
```

Se for enviar para o GitHub, crie o repositório como **privado**: a pasta contém o seu perfil e os seus casos. O plugin não faz push dessa pasta sem você pedir.

## Atualizar

```bash
claude plugin marketplace update direito-legal
claude plugin update direito-legal@direito-legal
```

O primeiro comando busca a lista mais recente. O segundo atualiza o plugin. Reinicie o Claude Code para a atualização valer. A sua pasta de dados não é alterada pela atualização.

## Privacidade

- **Os seus dados ficam só no seu computador.** O perfil, os casos e a base são arquivos na pasta de dados. O plugin não tem servidor próprio na internet e não coleta nada.
- **As perguntas passam pelo modelo.** Tudo o que você escreve é processado pelo Claude, como em qualquer uso do Claude Code. Valem as condições da sua conta.
- **O servidor local só acessa sites oficiais**, para baixar leis e conferir precedentes. Para pesquisar, o Claude também usa a busca na web do próprio Claude Code.
- **Não ponha dados de terceiros.** Nada de nome, documento ou história identificável de pacientes, clientes ou empregados. Use dados genéricos ou anonimizados.

## Qualidade e limites

### O que foi medido

Numa avaliação interna, o plugin respondeu a 50 questões de exames passados da 1ª fase da OAB, com gabarito oficial. Na rodada final, acertou 50 de 50, com 0 citações reprovadas pelo verificador e com tag de fonte em todas as linhas de fundamentos. Uma rodada anterior também acertou as 50, mas teve 3 citações reprovadas, corrigidas antes da rodada final.

As questões estão em [`evals/oab/questoes.jsonl`](evals/oab/questoes.jsonl) e cobrem cinco áreas: Processo Civil (14), Civil (12), Constitucional (10), Ética (8) e Consumidor (6).

### Por que isso não é garantia

- **As provas são públicas** e podem estar nos dados de treino do modelo. O resultado não garante acerto em casos novos.
- **Questão de prova não é caso real.** Ela traz todos os fatos e tem uma alternativa certa. Num caso real, faltam fatos e as provas importam.
- **São só 50 questões, em cinco áreas.** Trabalhista, penal, tributário e previdenciário não foram medidos.

### Limites conhecidos

- **A verificação confere a citação, não a interpretação.** O verificador confirma que o artigo, o inciso ou o parágrafo existe e não está revogado, e que a súmula ou o tema está registrado e vigente. Ele não garante que a conclusão tirada do texto está certa. O contraditor reduz esse risco, mas não o elimina.
- **O leitor do Planalto depende do HTML do site.** Se o Planalto mudar o formato das páginas, o download de leis pode falhar até o plugin ser ajustado. Nesse caso nada é gravado por cima da cópia boa.
- **A existência de acórdão avulso não é verificada.** Decisões individuais (REsp, RE, HC…) só passam com a URL `*.jus.br` da decisão na mesma linha ou com a tag `[conhecimento do modelo — verificar]`.
- **Sites de tribunais podem bloquear acesso automatizado.** Quando a página oficial não abre, o precedente fica registrado como não conferido e toda citação dele leva `[verificar]`.
- **Redações antigas são aproximadas.** Para fatos antigos, o plugin tenta achar a redação da lei que valia na data, mas só conhece o ano de cada alteração e avisa quando há incerteza.
- **As regras são instruções ao modelo.** O verificador de citações é código e é determinístico. O restante (formato, gatilhos, tags) depende de o modelo seguir as regras, o que ele faz quase sempre, mas não por garantia.
- **Consulta completa leva tempo.** Ela envolve busca, leitura, verificação e contraditor. Conte com um a alguns minutos por pergunta, e com um consumo do seu plano maior que o de uma pergunta comum.

## Para quem quer contribuir

Issues e pull requests são bem-vindos. Bons pontos de partida: lei que o leitor do Planalto não entende, citação que o verificador lê errado e novos casos de teste.

### Estrutura do repositório

| Caminho | Conteúdo |
|---|---|
| `.claude-plugin/marketplace.json` | Registro deste repositório como marketplace. |
| `plugin/.claude-plugin/plugin.json` | Manifesto do plugin, com a versão. |
| `plugin/.mcp.json` | Como o Claude Code inicia o servidor `base-juridica`. |
| `plugin/regras.md`, `plugin/marcadores.md` | Regras de conduta e tags de fonte, lidas por toda skill. |
| `plugin/skills/` | As skills `consulta`, `pesquisar` e `configurar`. |
| `plugin/agents/contraditor.md` | O agente contraditor. |
| `plugin/servidor/` | Servidor MCP em Python: código em `src/base_juridica/`, testes em `tests/`. |
| `evals/` | Questões da OAB, o executor da avaliação e os testes dele. |

Ferramentas do servidor (`server.py`):

| Ferramenta | Função |
|---|---|
| `configuracao` | Devolve os caminhos da pasta de dados. |
| `buscar` | Busca em artigos, categorias e precedentes da base. |
| `ler_artigo` | Texto oficial de um artigo, hoje ou numa data passada. |
| `listar_categorias`, `ler_categoria` | Lista e lê os assuntos já pesquisados. |
| `baixar_lei` | Baixa uma lei do Planalto, grava e indexa. |
| `baixar_precedente` | Registra súmula, súmula vinculante ou tema e confere o enunciado na página oficial. |
| `integrar` | Grava conteúdo numa categoria. Exige fontes. |
| `verificar_citacoes` | Confere as citações de um texto contra a base. |
| `atualizar` | Baixa a lei de novo e registra o que mudou. |

### Rodar a partir de um clone

```bash
git clone https://github.com/brenoavelheda/direito-legal
claude plugin marketplace add ./direito-legal
claude plugin install direito-legal@direito-legal
```

Para baixar de uma vez as 12 leis do catálogo:

```bash
cd direito-legal/plugin/servidor
uv run python -m base_juridica.cli baixar-acervo
```

Os comandos de terminal não leem o `settings.json` do Claude Code. Se você usa uma pasta de dados diferente da padrão, defina `DIREITO_LEGAL_DADOS` também no terminal.

### Testes

```bash
cd plugin/servidor
uv run pytest               # servidor
uv run pytest ../../evals   # testes da avaliação
```

Os testes não acessam a internet. Os poucos que acessam ficam de fora por padrão.

### Avaliação com custo

```bash
cd plugin/servidor
uv run python ../../evals/rodar.py --limite 5
```

Este comando passa cada questão da OAB pela skill `consulta`, chamando o `claude -p`. **Ele consome o seu plano ou os seus créditos.** Na rodada interna, a mediana ficou perto de US$ 0,80 por questão. Use `--limite` para começar pequeno.

| Opção | Efeito |
|---|---|
| `--limite N` | Roda só as N primeiras questões. |
| `--paralelo K` | Número de questões em paralelo (padrão: 3). |
| `--fumaca` | Roda também as suas perguntas de `<pasta de dados>/avaliacao/fumaca.md`. O modelo está em [`evals/fumaca.exemplo.md`](evals/fumaca.exemplo.md). |
| `--so-relatorio` | Não chama o modelo; só refaz o relatório. |

O relatório vai para `<pasta de dados>/avaliacao/resultados/`. A rodada passa quando tem acerto de 85% ou mais, 0 citações reprovadas e 0 linhas de fundamentos sem tag.

### Antes de abrir um PR

- Rode os dois conjuntos de testes.
- Não inclua dado pessoal em código, teste, exemplo ou issue.
- Mudança que deva chegar a quem já instalou precisa subir o campo `version` em [`plugin/.claude-plugin/plugin.json`](plugin/.claude-plugin/plugin.json). Sem isso, o comando de atualização não entrega a versão nova.

## Apoie o projeto

A lei parte do princípio de que todo cidadão a conhece: "Ninguém se escusa de cumprir a lei, alegando que não a conhece" ([Lei de Introdução às Normas do Direito Brasileiro, art. 3º](https://www.planalto.gov.br/ccivil_03/decreto-lei/del4657compilado.htm)). No direito penal é igual: "O desconhecimento da lei é inescusável" ([Código Penal, art. 21](https://www.planalto.gov.br/ccivil_03/decreto-lei/del2848compilado.htm)). Quem comete um crime responde por ele mesmo sem saber que era crime; o desconhecimento da lei, no máximo, atenua a pena (art. 65, II).

Na prática, conhecer a lei é muito difícil. São muitas normas, escritas em linguagem técnica e alteradas o tempo todo. O direito-legal quer democratizar o acesso à lei e facilitar o seu cumprimento: qualquer pessoa pode perguntar e receber a resposta com a fonte oficial.

O direito-legal é gratuito e vai continuar gratuito. Se ele foi útil para você, considere apoiar o projeto com qualquer valor. Toda contribuição é muito bem-vinda, e eu agradeço de verdade.

O apoio ajuda a pagar os custos de manter o plugin: a revisão periódica das leis, das regras e das rodadas de avaliação, e o desenvolvimento das funcionalidades sugeridas por quem usa.

Para ter uma ideia do custo: cada rodada completa de avaliação, com 60 perguntas, consome o equivalente a cerca de US$ 72 em uso do Claude, pelo preço da API. Até a primeira versão foram duas rodadas, que somaram US$ 144,63. Montar as quatro categorias do acervo custou mais US$ 10,18. Esses valores não incluem o uso durante o desenvolvimento nem as horas de trabalho.

- **GitHub Sponsors:** [github.com/sponsors/brenoavelheda](https://github.com/sponsors/brenoavelheda)
- **Pix:** `dev_bsouto@pm.me`

O apoio é ao desenvolvimento do software. Ele não dá direito a consulta jurídica nem a atendimento individual.

Obrigado!

## Licença e créditos

[Apache License 2.0](LICENSE).

Este projeto é obra derivada de [anthropics/claude-for-legal](https://github.com/anthropics/claude-for-legal): a estrutura de plugins, os guardrails e as skills foram traduzidos para o português e adaptados ao direito brasileiro e ao uso pessoal, sem advogado revisor. Veja o arquivo [`NOTICE`](NOTICE).
