#!/usr/bin/env python3
"""Transforma o JSON coletado da Câmara de Praia Grande no site estático do Radar.
Uso: python3 build.py dados.json saida/
"""
import json, re, sys, os, unicodedata, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from classificar import classificar, GRUPOS, ORDEM, REGRA_TEXTO
from collections import Counter, defaultdict
from datetime import date

BASE = "https://www.praiagrande.sp.leg.br"
PUB = BASE + "/dispositivo/ideCustom/camarapg_publico"
MESES = {m: i + 1 for i, m in enumerate(
    "janeiro fevereiro março abril maio junho julho agosto setembro outubro novembro dezembro".split())}

# Explicação simples de cada tipo de proposta
TIPOS = {
    "Indicações": ("Pedido ao prefeito", "Pede uma melhoria ou serviço à Prefeitura (asfalto, poda, iluminação...). A Prefeitura não é obrigada a atender."),
    "Requerimento": ("Pergunta ou cobrança", "Pede informações oficiais à Prefeitura ou a outro órgão. Precisa ser aprovado pelos vereadores."),
    "Moção": ("Moção", "Manifestação da Câmara: aplauso, apoio, repúdio ou pesar."),
    "Projeto de Lei": ("Projeto de lei", "Proposta de nova lei ou de mudança numa lei da cidade."),
    "Projeto de Lei Complementar": ("Projeto de lei complementar", "Lei sobre temas especiais (impostos, estatuto dos servidores, plano diretor...)."),
    "Projeto de Decreto Legislativo": ("Decreto legislativo", "Decisão da própria Câmara, como dar título de cidadão ou homenagens."),
    "Projeto de Resolução": ("Resolução", "Regra interna da Câmara."),
    "Proposta de Emenda à L.O.": ("Mudança na Lei Orgânica", "Altera a 'Constituição' da cidade."),
    "Emendas Impositivas": ("Emenda impositiva", "Indica para onde vai parte do orçamento da cidade; a Prefeitura deve cumprir."),
    "Emendas Orçamentárias": ("Emenda ao orçamento", "Propõe mudança no orçamento da cidade."),
}


def norm(s):
    s = unicodedata.normalize("NFD", s or "")
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", s).strip().upper()


def parse_data(s):
    m = re.match(r"(\d+) de (\w+) de (\d{4})", (s or "").strip(), re.I)
    if not m:
        return None
    mes = MESES.get(m.group(2).lower())
    return date(int(m.group(3)), mes, int(m.group(1))).isoformat() if mes else None


def parse_br(s):
    m = re.match(r"(\d\d)/(\d\d)/(\d{4})", s or "")
    return f"{m.group(3)}-{m.group(2)}-{m.group(1)}" if m else None


def titulo_caso(nome):
    peq = {"DE", "DA", "DO", "DOS", "DAS", "E"}
    return " ".join(w.capitalize() if w.upper() not in peq else w.lower() for w in nome.split())


def main(src, out):
    raw = json.load(open(src, encoding="utf-8"))
    os.makedirs(os.path.join(out, "dados"), exist_ok=True)

    # ---------- Vereadores ----------
    vereadores = []
    vistos_p = set()
    for p in raw["parlamentares"]:
        if p["codigo"] in vistos_p:
            continue
        vistos_p.add(p["codigo"])
        cells = p.get("cells", [])
        partido = cells[2] if len(cells) > 2 else ""
        sigla = partido.split(" (")[0].strip()
        det = p.get("detalhe", "")
        email = (re.search(r"E-mail:\s*([\w.\-+]+@[\w.\-]+)", det) or [None, ""])[1]
        # Só e-mail institucional (@praiagrande.sp.leg.br). Telefones não são publicados no Radar.
        if email and not email.lower().endswith("praiagrande.sp.leg.br"):
            email = ""
        ficha = {}
        for ano_blk in re.findall(r"Ano: (\d{4})(.*?)(?=Ano: \d{4}|$)", p.get("resumoMaterias", "").split("Co-Autor Total")[0]):
            ano, blk = ano_blk
            for sig, nome, n in re.findall(r"\b([A-Z]{2,6}) ([A-Za-zÀ-ú .\-]+?) (\d+)\b", blk):
                ficha.setdefault(ano, {})[nome.strip()] = int(n)
        vereadores.append({
            "id": p["codigo"],
            "nome": titulo_caso(p["nome"]),
            "nome_norm": norm(p["nome"]),
            "partido": sigla,
            "partido_nome": partido,
            "ativo": len(cells) > 3 and cells[3] == "Sim",
            "titular": len(cells) > 4 and cells[4] == "Sim",
            "foto": (BASE + p["foto"]) if p.get("foto", "").startswith("/") else p.get("foto", ""),
            "email": email,
            "ficha_oficial": ficha,
        })
    por_norm = {v["nome_norm"]: v for v in vereadores}
    for m in raw.get("mesa", []):
        if norm(m["nome"]) in por_norm:
            por_norm[norm(m["nome"])]["cargo"] = m["cargo"]

    # Suplentes que exerceram mandato mas não estão na lista oficial: autores de propostas
    # que também aparecem nas listas de presença das sessões.
    institucional = re.compile(r"EXECUTIVO|MESA|PODER|DIRETORIA|DEPARTAMENTO|COMISS|PREFEIT", re.I)
    pres_txt = norm(" ".join(s.get("presTxt", "") for s in raw["sessoes"]))
    for autor in sorted({m.get("autor", "") for m in raw["materias"]}):
        n = norm(autor)
        if not n or n in por_norm or institucional.search(autor) or (n + " /") not in pres_txt:
            continue
        partido = (re.search(re.escape(n) + r" / ([A-Z ]+?)(?= [A-Z]{3,} [A-Z]| [A-Z][a-z]|$)", pres_txt) or [None, ""])[1].strip()
        v = {"id": "s" + re.sub(r"[^a-z]", "", n.lower())[:20], "nome": titulo_caso(autor), "nome_norm": n,
             "partido": partido, "partido_nome": partido + " (suplente; fora da lista oficial de vereadores)", "ativo": False, "titular": False,
             "foto": "", "email": "", "ficha_oficial": {}, "fora_lista": True}
        vereadores.append(v); por_norm[n] = v

    # ---------- Propostas ----------
    props_por_ver = defaultdict(list)
    sem_vereador = Counter()
    tipos_total = Counter()
    grupos_total = Counter()
    grupos_cidade = Counter()
    vistos = set()
    for m in raw["materias"]:
        if m["c"] in vistos:
            continue
        vistos.add(m["c"])
        tipos_total[m["tipo"]] += 1
        g_all, _ = classificar(m["tipo"], m.get("ementa", ""))
        grupos_cidade[g_all] += 1
        autores = [a.strip() for a in re.split(r",|;| e (?=[A-ZÁÉÍÓÚ]{2,})", m.get("autor", "")) if a.strip()]
        alvo = [por_norm[norm(a)] for a in autores if norm(a) in por_norm]
        if not alvo:
            sem_vereador[m.get("autor", "") or "(sem autor)"] += 1
            continue
        g, sg = classificar(m["tipo"], m.get("ementa", ""))
        grupos_total[g] += 1
        num = re.search(r"Nº\s*([\d.]+)/(\d{4})", m.get("t", ""))
        reg = {
            "c": m["c"],
            "tp": m["tipo"],
            "n": num.group(1) if num else "",
            "a": num.group(2) if num else "",
            "d": parse_data(m.get("data")),
            "e": m.get("ementa", ""),
            "g": g,
            "sg": sg,
        }
        for i, v in enumerate(alvo):
            props_por_ver[v["id"]].append(dict(reg, pa=(i == 0)))  # pa = primeiro autor

    # ---------- Sessões e presença ----------
    sessoes = []
    for s in raw["sessoes"]:
        txt = s.get("presTxt", "")
        registrada = "Sem presen" not in txt and "Presentes" in txt
        corpo = norm(txt.split("Presentes", 1)[1]) if registrada else ""
        presentes = [v["id"] for v in vereadores if registrada and (v["nome_norm"] + " /") in corpo]
        aus_txt = s.get("ausTxt", "")
        justif = [v["id"] for v in vereadores if "Sem aus" not in aus_txt and v["nome_norm"] in norm(aus_txt)]
        sessoes.append({
            "c": s["codigo"],
            "t": s["titulo"],
            "d": parse_br(s["abertura"]),
            "tipo": s["nome_tipo"],
            "reg": registrada,
            "p": presentes,
            "j": justif,
            "o": [{"m": o["materia"].replace(" Autor:", "").strip(), "e": o.get("ementa", ""), "r": o["resultado"]} for o in s.get("ordem", [])],
        })
    sessoes.sort(key=lambda x: x["d"] or "")

    # ---------- Votos de cada vereador ----------
    COD = {"SIM": "S", "NAO": "N", "ABSTENCAO": "A", "NAO VOTOU": "X"}
    votacoes = []
    titulo_sessao = {s["codigo"]: (s["titulo"], parse_br(s["abertura"])) for s in raw["sessoes"]}
    for s in raw["sessoes"]:
        for vt in s.get("votacoes", []):
            t = norm(vt.get("texto", ""))
            if not t:
                continue
            votos = {}
            for v in vereadores:
                m = re.search(re.escape(v["nome_norm"]) + r" / [^/]*? - (NAO VOTOU|SIM|NAO|ABSTENCAO)\b", t)
                if m:
                    votos[v["id"]] = COD[m.group(1)]
            if not votos:
                continue
            num = re.search(r"VOTACAO DA MATERIA N\S* (\d+)", t)
            res = re.search(r"RESULTADO: (\w+)", t)
            tit, d = titulo_sessao.get(s["codigo"], (s.get("titulo", ""), parse_br(s.get("abertura", ""))))
            votacoes.append({"v": vt["v"], "s": s["codigo"], "st": tit, "d": d, "parte": vt.get("parte", "ordem"),
                             "m": re.sub(r"\s*Autor:.*$", "", vt.get("materia", "")).strip(), "mc": vt.get("materia_c", ""),
                             "e": re.sub(r"\s+", " ", vt.get("ementa", ""))[:240], "r": vt.get("resultado", ""), "x": votos})
    votacoes.sort(key=lambda x: (x["d"] or "", x["v"]), reverse=True)
    hoje = max((s["d"] for s in sessoes if s["d"]), default="")
    passadas = [s for s in sessoes if s["d"] and s["d"] <= raw.get("coletado_em", hoje)[:10]]

    # ---------- Resumo por vereador ----------
    resumo = []
    for v in vereadores:
        ps = props_por_ver.get(v["id"], [])
        cont = Counter(p["tp"] for p in ps if p["pa"])
        cont_coaut = Counter(p["tp"] for p in ps if not p["pa"])
        grp = Counter(p["g"] for p in ps if p["pa"])
        grp_ano = Counter((p["a"], p["g"]) for p in ps if p["pa"])
        por_ano = Counter((p["a"], p["tp"]) for p in ps if p["pa"])
        # presença: só sessões com lista registrada entre a 1ª e a última presença do vereador
        # Presença: só sessões com lista publicada. Quem esteve no cargo o período todo
        # (presente no início e no fim) é comparado com todas essas sessões; quem exerceu
        # só parte do período aparece só com o número de presenças, sem "de quantas",
        # porque o sistema não informa as datas exatas de posse, licença e saída.
        reg = [s for s in passadas if s["reg"]]
        mine = [s for s in reg if v["id"] in s["p"]]
        pres = len(mine)
        periodo_todo = bool(mine) and mine[-1]["d"] == reg[-1]["d"] and (
            date.fromisoformat(mine[0]["d"]) - date.fromisoformat(reg[0]["d"])).days <= 60
        janela = reg if periodo_todo else []
        just = sum(1 for s in janela if v["id"] in s["j"] and v["id"] not in s["p"])
        cv = Counter(vt["x"][v["id"]] for vt in votacoes if v["id"] in vt["x"])
        resumo.append({
            "votos": {k: cv.get(k, 0) for k in "SNAX"},
            **{k: v[k] for k in ("id", "nome", "partido", "partido_nome", "ativo", "titular", "foto", "email")},
            "periodo_todo": periodo_todo,
            "cargo": v.get("cargo", ""),
            "props": dict(cont),
            "grupos": dict(grp),
            "grupos_ano": {f"{a}|{g}": n for (a, g), n in grp_ano.items()},
            "coautor": dict(cont_coaut),
            "por_ano": {f"{a}|{t}": n for (a, t), n in por_ano.items()},
            "total": sum(cont.values()),
            "pres": pres,
            "pres_de": len(janela),
            "pres_just": just,
            "pres_ini": (janela or mine)[0]["d"] if (janela or mine) else None,
            "pres_fim": (janela or mine)[-1]["d"] if (janela or mine) else None,
            "parcial": not periodo_todo,
            "fora_lista": v.get("fora_lista", False),
            "ficha_oficial": v["ficha_oficial"],
        })
        with open(os.path.join(out, "dados", f"v{v['id']}.json"), "w", encoding="utf-8") as f:
            json.dump(sorted(ps, key=lambda p: p["d"] or "", reverse=True), f, ensure_ascii=False, separators=(",", ":"))

    # Fora do Radar: cadastros sem nenhuma presença e nenhuma proposta no período (ex.: registros antigos marcados como ativos)
    excluidos = [r["nome"] for r in resumo if r["total"] == 0 and r["pres"] == 0 and not r["coautor"]]
    resumo = [r for r in resumo if r["nome"] not in excluidos]
    reg_sess = [s for s in passadas if s["reg"]]
    sem_reg = [s for s in passadas if not s["reg"]]
    meta = {
        "coletado_em": raw.get("coletado_em"),
        "periodo": "2025–2026 (14ª legislatura)",
        "n_sessoes": len(passadas),
        "n_sessoes_reg": len(reg_sess),
        "sessoes_sem_reg": [{"c": s["c"], "t": s["t"], "d": s["d"]} for s in sem_reg],
        "ultima_presenca_registrada": reg_sess[-1]["d"] if reg_sess else None,
        "total_props": len(vistos),
        "tipos_total": dict(tipos_total),
        "props_sem_vereador": sum(sem_vereador.values()),
        "autores_externos": dict(sem_vereador.most_common(8)),
        "tipos_explica": {k: list(v) for k, v in TIPOS.items()},
        "grupos": {k: list(GRUPOS[k]) for k in ORDEM},
        "grupos_ordem": ORDEM,
        "grupos_cidade": dict(grupos_cidade),
        "regra": REGRA_TEXTO,
        "fonte": PUB,
        "excluidos": excluidos,
        "n_votacoes": len(votacoes),
    }
    meta["busca"] = build_busca(raw, out)
    with open(os.path.join(out, "dados", "resumo.json"), "w", encoding="utf-8") as f:
        json.dump({"meta": meta, "vereadores": resumo}, f, ensure_ascii=False, separators=(",", ":"))
    with open(os.path.join(out, "dados", "votos.json"), "w", encoding="utf-8") as f:
        json.dump(votacoes, f, ensure_ascii=False, separators=(",", ":"))
    with open(os.path.join(out, "dados", "sessoes.json"), "w", encoding="utf-8") as f:
        json.dump([{**s} for s in passadas], f, ensure_ascii=False, separators=(",", ":"))
    tpl = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")
    if os.path.exists(tpl) and os.path.abspath(tpl) != os.path.abspath(os.path.join(out, "index.html")):
        shutil.copy(tpl, os.path.join(out, "index.html"))
    print(json.dumps({k: meta[k] for k in ("excluidos", "n_votacoes", "n_sessoes", "n_sessoes_reg", "ultima_presenca_registrada", "total_props", "props_sem_vereador", "autores_externos")}, ensure_ascii=False, indent=1))





# ---------------- Passo 4: busca por bairro/rua e pedidos que voltam ----------------
def build_busca(raw, out):
    from enderecos import extrair, temas, chave_rua
    from collections import OrderedDict
    vistos = set()
    ruas, ruas_idx, bairros, bairros_idx, temas_l, temas_idx, autores, autores_idx = [], {}, [], {}, [], {}, [], {}
    def idx(lst, d, k):
        if k not in d:
            d[k] = len(lst); lst.append(k)
        return d[k]
    # nome canônico de cada rua = grafia mais comum entre as que têm a mesma chave
    grafias = defaultdict(Counter)
    linhas = []
    for m in raw["materias"]:
        if m["c"] in vistos or m["tipo"] not in ("Indicações", "Requerimento"):
            continue
        vistos.add(m["c"])
        rs, b = extrair(m.get("ementa", ""))
        for r in rs:
            grafias[chave_rua(r)][r] += 1
        linhas.append((m, rs, b, temas(m.get("ementa", ""))))
    canon = {k: c.most_common(1)[0][0] for k, c in grafias.items()}
    pedidos = []
    grupos = defaultdict(list)
    for m, rs, b, ts in linhas:
        num = re.search(r"Nº\s*([\d.]+)/(\d{4})", m.get("t", ""))
        d = parse_data(m.get("data"))
        ri = [idx(ruas, ruas_idx, canon[chave_rua(r)]) for r in rs]
        bi = idx(bairros, bairros_idx, b) if b else -1
        ti = [idx(temas_l, temas_idx, t) for t in ts]
        ai = idx(autores, autores_idx, titulo_caso(m.get("autor", "") or "Sem autor"))
        e = re.sub(r"\s+", " ", m.get("ementa", "")).strip()
        pedidos.append([m["c"], ai, d, 0 if m["tipo"] == "Indicações" else 1, ti, ri, bi, (num.group(1) + "/" + num.group(2)) if num else "", e[:220] + ("…" if len(e) > 220 else "")])
        for r in ri:
            for t in ti:
                if temas_l[t] != "Outros pedidos":
                    grupos[(r, t)].append(len(pedidos) - 1)
    # Pedidos que voltam: mesmo tema, mesma rua (e mesmo bairro, quando informado), 3+ pedidos em datas com 30+ dias de distância
    repetidos = []
    for (r, t), ps in grupos.items():
        por_bairro = defaultdict(list)
        for p in ps:
            por_bairro[pedidos[p][6]].append(p)
        conhecidos = [k for k in por_bairro if k != -1]
        if len(conhecidos) == 1 and -1 in por_bairro:  # sem bairro informado junta com o único bairro conhecido
            por_bairro[conhecidos[0]] += por_bairro.pop(-1)
        for bi, lst in por_bairro.items():
            datas = sorted(pedidos[p][2] for p in lst if pedidos[p][2])
            if len(lst) < 3 or not datas:
                continue
            if (date.fromisoformat(datas[-1]) - date.fromisoformat(datas[0])).days < 30:
                continue
            lst = sorted(lst, key=lambda p: pedidos[p][2] or "")
            repetidos.append({"r": r, "t": t, "b": bi, "n": len(lst), "p": lst,
                              "ini": datas[0], "fim": datas[-1], "na": len({pedidos[p][1] for p in lst})})
    repetidos.sort(key=lambda x: (-x["n"], x["fim"]), reverse=False)
    with open(os.path.join(out, "dados", "busca.json"), "w", encoding="utf-8") as f:
        json.dump({"ruas": ruas, "bairros": bairros, "temas": temas_l, "autores": autores, "pedidos": pedidos, "repetidos": repetidos},
                  f, ensure_ascii=False, separators=(",", ":"))
    com_rua = sum(1 for p in pedidos if p[5]); com_bairro = sum(1 for p in pedidos if p[6] >= 0)
    return {"n_pedidos": len(pedidos), "com_rua": com_rua, "com_bairro": com_bairro, "n_repetidos": len(repetidos),
            "n_ruas": len(ruas), "n_bairros": len(bairros)}


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
