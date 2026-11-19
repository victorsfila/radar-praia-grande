"""Projetos do Executivo (prefeito) e da Mesa Diretora, Atos da Mesa, e como os vereadores votaram neles."""
import json, os, re

PUB = "https://www.praiagrande.sp.leg.br/dispositivo/ideCustom/camarapg_publico"
EXEC = re.compile(r"executivo", re.I)
MESA = re.compile(r"mesa diretora|presidente da c[aâ]mara|gabinete da presid", re.I)


def build_poderes(raw, out, votacoes, parse_data):
    por_mat = {}
    for vt in votacoes:
        if vt.get("mc"):
            por_mat.setdefault(vt["mc"], []).append({"v": vt["v"], "d": vt["d"], "st": vt["st"], "r": vt["r"], "x": vt["x"], "m": vt["m"]})
    def item(m):
        num = re.search(r"Nº\s*([\d.]+)/(\d{4})", m.get("t", ""))
        return {"c": m["c"], "tp": m["tipo"], "n": num.group(1) if num else "", "a": num.group(2) if num else "",
                "d": parse_data(m.get("data")), "e": re.sub(r"\s+", " ", m.get("ementa", "")).strip(), "aut": m.get("autor", ""),
                "vot": sorted(por_mat.get(m["c"], []), key=lambda x: x["d"] or "")}
    vistos = set(); executivo, mesa = [], []
    for m in raw["materias"]:
        if m["c"] in vistos:
            continue
        vistos.add(m["c"])
        if EXEC.search(m.get("autor", "")):
            executivo.append(item(m))
        elif MESA.search(m.get("autor", "")):
            mesa.append(item(m))
    executivo.sort(key=lambda x: x["d"] or "", reverse=True); mesa.sort(key=lambda x: x["d"] or "", reverse=True)
    atos = sorted(raw.get("atos_mesa", []), key=lambda a: a["data"][6:] + a["data"][3:5] + a["data"][:2], reverse=True)
    dados = {"executivo": executivo, "mesa_props": mesa, "atos": atos, "mesa": raw.get("mesa", [])}
    with open(os.path.join(out, "dados", "poderes.json"), "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, separators=(",", ":"))
    return {"n_executivo": len(executivo), "n_exec_votados": sum(1 for x in executivo if x["vot"]), "n_mesa": len(mesa), "n_atos": len(atos)}
