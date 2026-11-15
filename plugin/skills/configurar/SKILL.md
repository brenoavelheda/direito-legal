---
name: configurar
description: Cria ou atualiza o perfil jurídico do usuário (perfil.md) e abre as pastas dos assuntos dele em casos/. Use na primeira vez que usar o direito-legal, ou quando o usuário disser "configurar", "atualizar meu perfil", "abrir caso", "novo caso", "registrar um assunto", "mudei de endereço", "contratei advogado".
---

# Configurar perfil e casos

## 1. Leia as regras e o perfil

- Leia `${CLAUDE_PLUGIN_ROOT}/regras.md` e `${CLAUDE_PLUGIN_ROOT}/marcadores.md`.
- Chame `configuracao` (servidor `base-juridica`) para saber a pasta de dados.
- Leia o `perfil.md` da pasta de dados, se existir.
- Liste a pasta `casos/` da pasta de dados.

## 2. Monte o perfil

`perfil.md` tem estes campos. Pré-preencha com o que já se sabe; pergunte **só** o que faltar ou o que o usuário pediu para mudar, numa única mensagem curta.

```markdown
# Perfil

- **Nome:** …
- **Situação:** pessoa física; profissão; tem PJ? (regime tributário)
- **Domicílio:** cidade/UF (define foro e juizados)
- **É advogado?** não → peticionar só nas exceções listadas em regras.md
- **Como usa:** onde usa o Claude Code (PC, celular)
- **Advogado contratado:** por assunto, se houver

## Assuntos atuais
| Assunto | Caso (`casos/<slug>`) | Situação em uma linha |
|---|---|---|

## Preferências de resposta
- português, direto, tabelas quando ajudarem
- documentos em .docx (lib `docx`, Node)
```

## 3. Abra os casos

Para cada assunto atual sem pasta, crie `casos/<slug>/` na pasta de dados com:

- `fatos.md` — fatos como o usuário relatou, com data de cada relato; separe **fatos** de **suposições**;
- `cronologia.md` — tabela `| Data | Evento | Fonte (relato / documento) |`;
- `historico.md` — registro das consultas feitas sobre o caso (a skill `consulta` anexa aqui);
- `documentos/` — PDFs e arquivos que o usuário colocar (crie com um `.gitkeep`).

O slug é curto, em minúsculas, sem acento (ex.: `execucao-financiamento`, `locacao-apartamento`).

## 4. Limites

- Nada de dado pessoal identificável de terceiros (pacientes, clientes) em `perfil.md` ou `casos/`.
- Não grave nada em `base/` (isso é só pela ferramenta `integrar`).
- Termine listando o que foi criado ou alterado e o que ficou em aberto.
