"""Roda a avaliação: cada questão da OAB passa pela skill consulta
(`claude -p "/direito-legal:consulta [avaliação] …"`) e o relatório vai para
<dados>/avaliacao/resultados/<AAAA-MM-DD>.md, onde <dados> é a pasta de dados
do usuário (DIREITO_LEGAL_DADOS).

    cd plugin/servidor
    uv run python ../../evals/rodar.py [--limite N] [--paralelo K] [--fumaca] [--so-relatorio]

--fumaca roda também as perguntas de <dados>/avaliacao/fumaca.md (perguntas
reais do usuário; modelo em evals/fumaca.exemplo.md). As respostas ficam em
<dados>/avaliacao/resultados/respostas-<data>.jsonl; uma nova execução no
mesmo dia pula as questões já respondidas sem erro.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from conferir import (  # noqa: E402
    citacoes_reprovadas, contraditor_alterou, linhas_fundamentos, linhas_sem_tag, pontuar,
)

from base_juridica.config import Config, load_config  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
EVALS = RAIZ / "evals"
TIMEOUT_S = 40 * 60

# A avaliação lê a web (WebFetch) em dezenas de sessões sem ninguém olhando:
# só leitura, a base pelo MCP e a skill/contraditor. Nada de shell nem escrita.
_MCP = "mcp__plugin_direito-legal_base-juridica__"
FERRAMENTAS_PERMITIDAS = [
    *(_MCP + f for f in ("configuracao", "buscar", "ler_artigo", "listar_categorias", "ler_categoria", "baixar_lei",
                         "baixar_precedente", "integrar", "verificar_citacoes", "atualizar")),
    "WebSearch", "WebFetch", "Read", "Glob", "Grep", "Agent", "Skill",
]
FERRAMENTAS_PROIBIDAS = ["Bash", "PowerShell", "Write", "Edit", "NotebookEdit"]


def _comando(exe: str, prompt: str) -> list[str]:
    return [exe, "-p", prompt, "--output-format", "json", "--permission-mode", "default",
            "--allowedTools", ",".join(FERRAMENTAS_PERMITIDAS),
            "--disallowedTools", ",".join(FERRAMENTAS_PROIBIDAS)]


def _prompt_oab(q: dict) -> str:
    alternativas = "\n".join(f"{letra}) {texto}" for letra, texto in sorted(q["alternativas"].items()))
    return (f"/direito-legal:consulta [avaliação] Questão de múltipla escolha (OAB, 1ª fase, área: {q['area']}).\n\n"
            f"{q['enunciado']}\n\n{alternativas}\n\n"
            "Responda no formato fixo da consulta e termine com a linha ALTERNATIVA: <letra>.")


def _prompt_fumaca(pergunta: str) -> str:
    return f"/direito-legal:consulta [avaliação] {pergunta}"


def _chamar_claude(prompt: str, cwd: Path) -> dict:
    exe = shutil.which("claude")
    if exe is None:
        return {"erro": "claude não encontrado no PATH"}
    inicio = time.time()
    try:
        proc = subprocess.run(
            _comando(exe, prompt),
            # stdin fechado: o claude -p anexa o stdin ao prompt.
            cwd=cwd, stdin=subprocess.DEVNULL, capture_output=True, timeout=TIMEOUT_S,
            encoding="utf-8", errors="replace",
        )
    except subprocess.TimeoutExpired:
        return {"erro": f"timeout de {TIMEOUT_S}s", "duracao_s": round(time.time() - inicio)}
    saida = {"duracao_s": round(time.time() - inicio)}
    try:
        dados = json.loads(proc.stdout)
    except ValueError:
        saida["erro"] = f"saída não-JSON (exit {proc.returncode}): {proc.stdout[-500:]} {proc.stderr[-500:]}"
        return saida
    saida["resposta"] = dados.get("result", "")
    saida["custo_usd"] = dados.get("total_cost_usd")
    if dados.get("is_error"):
        saida["erro"] = f"is_error: {saida['resposta'][:300]}"
    return saida


def _ler_jsonl(caminho: Path) -> list[dict]:
    if not caminho.exists():
        return []
    return [json.loads(l) for l in caminho.read_text(encoding="utf-8").splitlines() if l.strip()]


def _chave(r: dict) -> str:
    return r.get("chave") or f"{r.get('exame')}-{r.get('numero')}"


def executar(itens: list[dict], respostas_path: Path, paralelo: int, cwd: Path) -> None:
    feitas = {_chave(r) for r in _ler_jsonl(respostas_path) if not r.get("erro")}
    pendentes = [i for i in itens if i["chave"] not in feitas]
    print(f"{len(itens)} itens, {len(itens) - len(pendentes)} já respondidos, {len(pendentes)} a rodar", flush=True)
    trava = threading.Lock()

    def um(item: dict) -> None:
        r = _chamar_claude(item["prompt"], cwd)
        registro = {k: v for k, v in item.items() if k != "prompt"} | r
        with trava:
            with respostas_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(registro, ensure_ascii=False) + "\n")
            status = "ERRO " + r["erro"][:80] if r.get("erro") else "ok"
            print(f"[{time.strftime('%H:%M:%S')}] {item['chave']} {status} ({r.get('duracao_s')}s)", flush=True)

    with ThreadPoolExecutor(max_workers=paralelo) as pool:
        list(pool.map(um, pendentes))


def _ultimas(respostas_path: Path) -> dict[str, dict]:
    ultimas: dict[str, dict] = {}
    for r in _ler_jsonl(respostas_path):
        if _chave(r) not in ultimas or not r.get("erro"):
            ultimas[_chave(r)] = r
    return ultimas


def relatorio(questoes: list[dict], fumaca: list[str], respostas_path: Path, cfg: Config, destino: Path) -> dict:
    ultimas = _ultimas(respostas_path)
    por_area: dict[str, list[bool]] = defaultdict(list)
    total_linhas = sem_tag_total = reprovadas_total = alterou = respondidas = erros = 0
    detalhes = []
    for q in questoes:
        r = ultimas.get(q["chave"])
        if r is None:
            continue
        if r.get("erro"):
            erros += 1
            detalhes.append(f"- {q['chave']} ({q['area']}): **erro** — {r['erro'][:200]}")
            continue
        resposta = r.get("resposta", "")
        respondidas += 1
        acertou = pontuar(resposta, q["gabarito"])
        if not q.get("lei_mudou"):
            por_area[q["area"]].append(acertou)
        linhas = linhas_fundamentos(resposta)
        sem_tag = linhas_sem_tag(resposta)
        reprovadas = citacoes_reprovadas(cfg, resposta)
        total_linhas += len(linhas)
        sem_tag_total += len(sem_tag)
        reprovadas_total += len(reprovadas)
        alterou += contraditor_alterou(resposta)
        problemas = []
        if not acertou:
            problemas.append(f"errou (gabarito {q['gabarito']})")
        problemas += [f"sem tag: `{l[:120]}`" for l in sem_tag]
        problemas += [f"citação {v.status}: `{v.citacao.trecho[:80]}` — {v.detalhe[:120]}" for v in reprovadas]
        if problemas:
            detalhes.append(f"- {q['chave']} ({q['area']}{', lei mudou' if q.get('lei_mudou') else ''}): "
                            + "; ".join(problemas))

    acertos = sum(sum(v) for v in por_area.values())
    contadas = sum(len(v) for v in por_area.values())
    taxa = acertos / contadas if contadas else 0.0
    pct_tag = (total_linhas - sem_tag_total) / total_linhas if total_linhas else 0.0

    fumaca_linhas = []
    for i, pergunta in enumerate(fumaca, 1):
        r = ultimas.get(f"fumaca-{i}")
        if r is None:
            continue
        resp = r.get("resposta", "")
        tem = {
            "fonte": bool(linhas_fundamentos(resp)) and not linhas_sem_tag(resp),
            "certeza": "## Certeza:" in resp,
            "próximos passos": "## Próximos passos" in resp,
        }
        marca = " · ".join(f"{k}: {'sim' if v else 'NÃO'}" for k, v in tem.items())
        fumaca_linhas.append(f"| {i} | {pergunta[:70]} | {marca} |")

    criterios = {
        "acerto ≥ 85% (lei_mudou=false)": taxa >= 0.85,
        "0 citações reprovadas": reprovadas_total == 0,
        "0 linhas de Fundamentos sem tag": sem_tag_total == 0,
    }
    linhas_md = [
        f"# Avaliação v1a — {date.today().isoformat()}",
        "",
        f"- Questões respondidas: {respondidas} (erros de execução: {erros})",
        f"- **Acerto (lei_mudou=false): {acertos}/{contadas} = {taxa:.0%}**",
        f"- Linhas de Fundamentos com tag: {total_linhas - sem_tag_total}/{total_linhas} = {pct_tag:.0%}",
        f"- Citações reprovadas pelo verificar_citacoes: {reprovadas_total}",
        f"- Respostas que o contraditor alterou: {alterou}",
        "",
        "## Critérios de aceitação",
        "",
        "| Critério | Resultado |",
        "|---|---|",
        *(f"| {k} | {'passou' if v else 'FALHOU'} |" for k, v in criterios.items()),
        "",
        "## Acerto por área",
        "",
        "| Área | Acertos | Total | % |",
        "|---|---|---|---|",
        *(f"| {a} | {sum(v)} | {len(v)} | {sum(v) / len(v):.0%} |" for a, v in sorted(por_area.items())),
        "",
        "## Problemas por questão",
        "",
        *(detalhes or ["Nenhum."]),
    ]
    if fumaca_linhas:
        linhas_md += ["", "## Teste de fumaça (perguntas reais)", "", "| # | Pergunta | Critérios |", "|---|---|---|",
                      *fumaca_linhas]
    destino.write_text("\n".join(linhas_md) + "\n", encoding="utf-8")
    return {"taxa": taxa, "reprovadas": reprovadas_total, "sem_tag": sem_tag_total, "criterios": criterios}


def _fumaca(arquivo: Path) -> list[str]:
    texto = arquivo.read_text(encoding="utf-8")
    return [m.group(1).strip() for l in texto.splitlines() if (m := re.match(r"^\s*\d+\.\s+(.+)", l))]


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # console do Windows é cp1252 ("≥" quebrava o print)
    p = argparse.ArgumentParser()
    p.add_argument("--limite", type=int, default=None, help="roda só as N primeiras questões")
    p.add_argument("--paralelo", type=int, default=3)
    p.add_argument("--fumaca", action="store_true", help="roda também as perguntas de <dados>/avaliacao/fumaca.md")
    p.add_argument("--so-relatorio", action="store_true", help="não chama o claude; só refaz o relatório")
    p.add_argument("--data", default=date.today().isoformat())
    args = p.parse_args(argv)

    cfg = load_config()
    avaliacao = cfg.dados_dir / "avaliacao"
    questoes = [q | {"chave": f"{q['exame']}-{q['numero']}"}
                for q in _ler_jsonl(EVALS / "oab" / "questoes.jsonl")]
    if args.limite:
        questoes = questoes[: args.limite]
    fumaca = _fumaca(avaliacao / "fumaca.md") if (avaliacao / "fumaca.md").exists() else []
    respostas = avaliacao / "resultados" / f"respostas-{args.data}.jsonl"
    respostas.parent.mkdir(parents=True, exist_ok=True)

    if not args.so_relatorio:
        itens = [q | {"prompt": _prompt_oab(q)} for q in questoes]
        if args.fumaca:
            itens += [{"chave": f"fumaca-{i}", "pergunta": f, "prompt": _prompt_fumaca(f)}
                      for i, f in enumerate(fumaca, 1)]
        executar(itens, respostas, args.paralelo, cfg.dados_dir)

    r = relatorio(questoes, fumaca, respostas, cfg, avaliacao / "resultados" / f"{args.data}.md")
    print(json.dumps({"taxa": round(r["taxa"], 3), "reprovadas": r["reprovadas"], "sem_tag": r["sem_tag"],
                      "criterios": r["criterios"]}, ensure_ascii=False))
    return 0 if all(r["criterios"].values()) else 1


if __name__ == "__main__":
    sys.exit(main())
