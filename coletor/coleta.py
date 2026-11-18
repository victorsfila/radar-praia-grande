#!/usr/bin/env python3
"""Coletor do Radar Praia Grande.

Baixa do sistema público da Câmara Municipal de Praia Grande-SP:
vereadores, sessões (presença, ordem do dia e votos de cada vereador) e propostas.
Grava um JSON no mesmo formato que o build.py usa.

Uso: python3 coleta.py saida.json [--anos 2025,2026]

Coleta devagar (pausa entre páginas) e se identifica no User-Agent.
"""
import json, re, sys, time, argparse
from datetime import datetime, timezone
import requests
from bs4 import BeautifulSoup

BASE = "https://www.praiagrande.sp.leg.br/dispositivo/ideCustom/camarapg_publico/"
UA = "RadarPraiaGrande/1.0 (projeto independente de transparencia; https://victorsfila.github.io/radar-praia-grande/)"
PAUSA = 1.0  # segundos entre páginas

S = requests.Session()
S.headers.update({"User-Agent": UA})


def get(path, data=None):
    for tentativa in range(4):
        try:
            r = S.post(BASE + path, data=data, timeout=60) if data is not None else S.get(BASE + path, timeout=60)
            r.raise_for_status()
            time.sleep(PAUSA)
            return r.content.decode("iso-8859-1")
        except Exception as e:  # noqa
            print(f"  tentativa {tentativa + 1} falhou em {path}: {e}", file=sys.stderr)
            time.sleep(10 * (tentativa + 1))
    raise RuntimeError("falhou: " + path)


def sopa(html):
    s = BeautifulSoup(html, "html.parser")
    for t in s(["style", "script", "header", "nav"]):
        t.decompose()
    return s


def texto(el):
    return re.sub(r"\s+", " ", el.get_text(" ") if el else "").strip()


def depois_de(t, marca):
    i = t.find(marca)
    return t[i:] if i >= 0 else t


def campo(row, rotulo):
    for p in row.find_all("p"):
        b = p.find("b")
        if b and texto(b).startswith(rotulo):
            return re.sub(r"^:\s*", "", texto(p).replace(rotulo, "", 1)).strip()
    return ""


def parlamentares():
    s = sopa(get("parlamentares/listagem.php"))
    out, vistos = [], set()
    for tr in s.find_all("tr"):
        a = tr.find("a", href=re.compile("detalhes_parlamentar"))
        if not a:
            continue
        cod = re.search(r"codigo=(\d+)", a["href"]).group(1)
        if cod in vistos:
            continue
        vistos.add(cod)
        img = tr.find("img")
        out.append({"codigo": cod, "nome": texto(a), "cells": [texto(td) for td in tr.find_all("td")], "foto": img["src"] if img else ""})
    for p in out:
        t = texto(sopa(get(f"parlamentares/detalhes_parlamentar.php?codigo={p['codigo']}")).body)
        t = depois_de(t, "Detalhes do Parlamentar")[:700]
        # não guardamos telefones: só o e-mail é usado no site
        p["detalhe"] = re.sub(r"Telefone:.*?(?=E-mail:)", "Telefone: ", t)
        t = texto(sopa(get(f"parlamentares/materias.php?codigo={p['codigo']}")).body)
        p["resumoMaterias"] = depois_de(t, "Primeiro Autor")[:900]
    return out


def mesa():
    """Composição atual da Mesa Diretora (presidente, vice, secretários)."""
    s = sopa(get("mesa_diretora/listagem.php"))
    out = []
    for tr in s.find_all("tr"):
        tds = [texto(td) for td in tr.find_all("td")]
        if len(tds) >= 4 and tds[-1] and tds[1]:
            out.append({"nome": tds[1], "cargo": tds[-1]})
    return out


def sessoes(anos):
    lista = []
    for ano in anos:
        off = 0
        while True:
            j = json.loads(get("info.sessoes.php", data={"ano": ano, "offset": off}))
            lista += j["sessoes"]
            if len(j["sessoes"]) < 50:
                break
            off += 1
    lista = list({s["codigo"]: s for s in lista}.values())
    for s in lista:
        c = s["codigo"]
        s["presTxt"] = depois_de(texto(sopa(get(f"sessao/presencas.php?codigo={c}")).body), "Resumo")[:1500]
        s["ausTxt"] = depois_de(texto(sopa(get(f"sessao/ausencias.php?codigo={c}")).body), "Resumo")[:1500]
        s["ordem"], s["votacoes"] = [], []
        for pg, parte in (("materias.php", "ordem"), ("materias_expediente.php", "expediente")):
            soup = sopa(get(f"sessao/{pg}?codigo={c}"))
            for tr in soup.find_all("tr"):
                tds = tr.find_all("td")
                if len(tds) < 3:
                    continue
                cel = [texto(td) for td in tds]
                if parte == "ordem":
                    s["ordem"].append({"n": cel[0], "materia": cel[1][:300], "ementa": cel[2][:300], "resultado": cel[-1][:120]})
                av = tr.find("a", href=re.compile("result_votacao"))
                if not av:
                    continue
                mat = tr.find("a", href=re.compile(r"detalhes_materia\.php"))
                vt = texto(sopa(get("sessao/" + av["href"].lstrip("./"))).body)
                i = re.search(r"Vota[çc][ãa]o d", vt)
                s["votacoes"].append({"parte": parte, "v": re.search(r"codigo=(\d+)", av["href"]).group(1),
                                      "materia_c": re.search(r"codigo=(\d+)", mat["href"]).group(1) if mat else "",
                                      "materia": texto(mat), "ementa": cel[2][:400], "resultado": cel[-1][:120],
                                      "texto": vt[i.start():][:2500] if i else ""})
    return lista


def materias(anos):
    out, totais = [], {}
    for ano in anos:
        pagina, paginas = 1, 1
        while pagina <= paginas:
            s = sopa(get(f"materias_leg/result_materias.php?ano_materia={ano}&offset={pagina}"))
            if pagina == 1:
                m = re.search(r"(\d+)", texto(s.find(class_="page-header")))
                totais[ano] = int(m.group(1)) if m else 0
                paginas = -(-totais[ano] // 50)
            for det in s.select(".details"):
                row = det.find_parent("tr")
                a = row.select_one("td a.result")
                pdf = row.find("a", href=re.compile(r"\.pdf$"))
                out.append({"c": det["data-codigo"], "t": texto(a), "tipo": campo(row, "Tipo"), "autor": campo(row, "Autor"),
                            "data": campo(row, "Data de apresentação"), "ementa": campo(row, "Ementa"), "pdf": pdf["href"] if pdf else ""})
            print(f"  propostas {ano}: página {pagina}/{paginas}", file=sys.stderr)
            pagina += 1
    return out, totais


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("saida")
    ap.add_argument("--anos", default=",".join(str(a) for a in range(2025, datetime.now().year + 1)))  # legislatura 2025–2028
    a = ap.parse_args()
    anos = [int(x) for x in a.anos.split(",")]
    print("vereadores…", file=sys.stderr); P = parlamentares()
    print("mesa diretora…", file=sys.stderr); MD = mesa()
    print("sessões…", file=sys.stderr); SS = sessoes(anos)
    print("propostas…", file=sys.stderr); M, T = materias(anos)
    dados = {"coletado_em": datetime.now(timezone.utc).isoformat(), "fonte": BASE, "parlamentares": P, "mesa": MD, "sessoes": SS, "materias": M,
             **{f"total{k}": v for k, v in T.items()}}
    json.dump(dados, open(a.saida, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"ok: {len(P)} vereadores, {len(SS)} sessões, {len(M)} propostas", file=sys.stderr)


if __name__ == "__main__":
    main()
