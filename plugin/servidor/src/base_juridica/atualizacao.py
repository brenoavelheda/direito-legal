"""Atualidade das leis (regra dos dias de validade), diff e redação vigente em data."""

from __future__ import annotations

import re
import urllib.request
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

from .arquivos import gravar_atomico, trava
from .captura import CapturaFalhou, FonteNaoOficial
from .catalogo import ReferenciaDesconhecida, item_do_catalogo
from .config import Config
from .indice import indexar_lei
from .leis import baixar_lei, carregar_lei
from .modelos import Artigo, LeiDoc
from .planalto import ParseVazio, rotulo

HISTORICO = "historico-normativo.md"
RE_ANO = re.compile(r"\b(1[89]\d{2}|20\d{2})\b")


@dataclass
class Diff:
    alterados: list[str] = field(default_factory=list)
    incluidos: list[str] = field(default_factory=list)
    removidos: list[str] = field(default_factory=list)

    def vazio(self) -> bool:
        return not (self.alterados or self.incluidos or self.removidos)


def _diff(antigo: LeiDoc, novo: LeiDoc) -> Diff:
    velhos = {a.numero: a for a in antigo.artigos}
    novos = {a.numero: a for a in novo.artigos}
    return Diff(
        alterados=[n for n in novos if n in velhos
                   and (novos[n].texto, novos[n].revogado) != (velhos[n].texto, velhos[n].revogado)],
        incluidos=[n for n in novos if n not in velhos],
        removidos=[n for n in velhos if n not in novos],
    )


def _registrar_historico(cfg: Config, lei_id: str, d: Diff, quando: datetime) -> None:
    caminho = cfg.base_dir / HISTORICO
    atual = caminho.read_text(encoding="utf-8") if caminho.exists() else "# Histórico normativo\n"
    lista = lambda xs: ", ".join(xs) or "—"  # noqa: E731
    entrada = (f"\n## {quando.date().isoformat()} {lei_id}\n\n- Alterados: {lista(d.alterados)}\n"
               f"- Incluídos: {lista(d.incluidos)}\n- Removidos: {lista(d.removidos)}\n")
    gravar_atomico(caminho, atual.rstrip("\n") + "\n" + entrada)


def atualizar_lei(cfg: Config, lei_id: str, *, abrir=urllib.request.urlopen) -> Diff:
    """Recaptura a lei; se o parse falhar, a cópia anterior fica intacta."""
    with trava(cfg.base_dir):
        antigo = carregar_lei(cfg, lei_id)
        ref = lei_id if item_do_catalogo(lei_id) else antigo.url
        novo = baixar_lei(cfg, ref, abrir=abrir)
        indexar_lei(cfg, novo)
        d = _diff(antigo, novo)
        if not d.vazio():
            _registrar_historico(cfg, lei_id, d, novo.capturado_em)
        return d


def garantir_atual(cfg: Config, lei_id: str, *, agora: datetime | None = None,
                   abrir=urllib.request.urlopen) -> tuple[LeiDoc, bool]:
    """Devolve (doc, desatualizado). Cópia mais velha que cfg.stale_days é recapturada;
    se a recaptura falhar, devolve a cópia anterior com desatualizado=True."""
    doc = carregar_lei(cfg, lei_id)
    agora = agora or datetime.now(timezone.utc)
    if agora - doc.capturado_em <= timedelta(days=cfg.stale_days):
        return doc, False
    try:
        atualizar_lei(cfg, lei_id, abrir=abrir)
    except (CapturaFalhou, ParseVazio, FonteNaoOficial, ReferenciaDesconhecida):
        return doc, True
    return carregar_lei(cfg, lei_id), False


def _ano_revogacao(art: Artigo) -> int | None:
    for nota in art.notas:
        if "revogad" in nota.lower():
            anos = RE_ANO.findall(nota)
            if anos:
                return int(anos[-1])
    return None


def _redacao_de_revogado(art: Artigo, data: date) -> tuple[str, bool]:
    """Artigo revogado: a última redação vale até o ano da revogação (nota)."""
    revogacao = _ano_revogacao(art)
    ultima = len(art.redacoes_anteriores) - 1
    linha_do_tempo = []  # (ano em que deixou de valer, texto)
    for i, r in enumerate(art.redacoes_anteriores):
        ano = r.data.year if r.data else (revogacao if i == ultima else None)
        linha_do_tempo.append((ano, r.texto))
    incerto = any(ano is None for ano, _ in linha_do_tempo)
    for ano, texto in linha_do_tempo:
        if ano is None:
            continue
        if data.year < ano:
            return texto, incerto
        if data.year == ano:
            return texto, True
    if revogacao is None:
        return "", True
    if not art.redacoes_anteriores and data.year <= revogacao:
        return "", True
    return "", incerto


def redacao_em(art: Artigo, data: date) -> tuple[str, bool]:
    """O artigo inteiro como estava na data: cada dispositivo (caput, §, inciso)
    na redação que valia, sem os incluídos depois. incerto=True quando a data
    cai no ano de uma alteração (só o ano é conhecido), quando há redação sem
    data ou quando o Planalto registra alteração sem guardar o texto antigo."""
    if art.revogado:
        return _redacao_de_revogado(art, data)
    ano = data.year
    incerto = False

    inclusao = [m.ano for m in art.marcos if m.rotulo == "caput" and m.tipo == "incluido"]
    if inclusao and ano < min(inclusao):
        return "", False
    if inclusao and ano == min(inclusao):
        incerto = True

    antigas: dict[str, list[tuple[int | None, str]]] = {}
    for r in art.redacoes_anteriores:
        antigas.setdefault(rotulo(r.texto) or "caput", []).append((r.data.year if r.data else None, r.texto))

    def antiga_na_data(rot: str) -> str | None:
        nonlocal incerto
        for deixou_de_valer, texto in antigas.get(rot, []):
            if deixou_de_valer is None:
                incerto = True
                continue
            if ano < deixou_de_valer:
                return texto
            if ano == deixou_de_valer:
                incerto = True
                return texto
        return None

    linhas = art.texto.split("\n") if art.texto else []
    rotulos = ["caput"] + [rotulo(l) for l in linhas[1:]]
    saida: list[str] = []
    vistos: set[str] = set()
    for rot, linha in zip(rotulos, linhas):
        primeira = rot not in vistos
        vistos.add(rot)
        antiga = antiga_na_data(rot) if rot and primeira else None
        if antiga is not None:
            saida.append(antiga)
            continue
        incluido = [m.ano for m in art.marcos if m.rotulo == rot and m.tipo == "incluido"]
        if rot != "caput" and incluido:
            if ano < min(incluido):
                continue  # o dispositivo ainda não existia
            if ano == min(incluido):
                incerto = True
        alterado = [m.ano for m in art.marcos if m.rotulo == rot and m.tipo == "redacao"]
        if alterado and ano < max(alterado) and not antigas.get(rot):
            incerto = True  # mudou depois da data, e o texto antigo não está na página
        saida.append(linha)
    # Dispositivos que não existem mais (revogados), mas valiam na data.
    for rot in antigas:
        if rot not in vistos:
            antiga = antiga_na_data(rot)
            if antiga is not None:
                saida.append(antiga)
    return "\n".join(saida), incerto
