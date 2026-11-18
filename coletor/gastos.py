"""Gastos da Câmara (contratos, despesas/empenhos, diárias e adiantamentos).
Fonte: API de dados abertos do Portal da Transparência da Câmara (Etransparência).
Gera site/dados/gastos.json.
"""
import json, re, os, unicodedata
from collections import defaultdict, Counter

PORTAL = "https://leideacesso.etransparencia.com.br/praiagrande.camara.sp/"


def _sa(s):
    return "".join(c for c in unicodedata.normalize("NFD", s or "") if unicodedata.category(c) != "Mn").lower()


CATEGORIAS = [  # (categoria, padrão na natureza da despesa) — a primeira que casar vale
    ("Pessoal, encargos e benefícios", r"salario|pessoal civil|proventos|ferias|gratifica|incorpora|licenca premio|vencimentos|subsidios|fgts|inss|previd|rpps|atuarial|salario-familia|auxilio|indenizacao auxilio"),
    ("Publicidade e divulgação", r"publicidade|propaganda|graficos e editoriais"),
    ("Diárias, viagens e adiantamentos", r"diarias"),
    ("Mão de obra terceirizada e vigilância", r"locacao de mao de obra|outras locacoes de mao|apoio administrativo|vigilancia"),
    ("Tecnologia e comunicações", r"software|tecnologia|processamento de dados|telecomunica|telefonia|comunicacoes|\btic\b"),
    ("Consultorias, cursos e serviços técnicos", r"assessoria|consultoria|tecnicos profissionais|estudos e projetos|selecao e treinamento|exposicoes|outros servicos de terceiros"),
    ("Contas, seguros e taxas", r"agua e esgoto|energia eletrica|seguros|bancarios|taxa de administracao|assinaturas|juros|multas"),
    ("Manutenção, materiais e equipamentos", r"manutencao|material|equipamento|mobiliario|maquinas|aparelhos|bandeiras|combustiveis|generos|alimentacao|utensilios"),
]
_CAT = [(c, re.compile(p)) for c, p in CATEGORIAS]


def categoria(natureza):
    n = _sa(natureza)
    for c, r in _CAT:
        if r.search(n):
            return c
    return "Outros"


def num(v):
    try:
        return float(str(v).replace(",", "."))
    except Exception:
        return 0.0


def separa_credor(s):
    """'Nome  (CNPJ ou CPF)' -> (nome, documento mascarado se for CPF)."""
    m = re.match(r"^(.*?)\s*\(([\d./-]+)\)\s*$", s or "")
    nome, doc = (m.group(1).strip(), m.group(2)) if m else ((s or "").strip(), "")
    if re.fullmatch(r"\d{3}\.\d{3}\.\d{3}-\d{2}", doc):  # CPF de pessoa física: mascara (LGPD)
        doc = "***" + doc[3:11] + "-**"
    return nome, doc


def build_gastos(raw_gastos, out):
    if not raw_gastos:
        return None
    anos = {}
    empenhos, contratos, diarias = [], [], []
    for ano, mods in sorted(raw_gastos.items()):
        ano = str(ano)
        vgm_nums = {d.get("Nro Empenho") for d in mods.get("VGM", [])}
        por_emp = defaultdict(list)
        for d in mods.get("DSP", []):
            por_emp[d.get("Nro Empenho")].append(d)
        tot = Counter(); cat_v = Counter(); mod_v = defaultdict(lambda: [0, 0.0]); forn = defaultdict(lambda: [0.0, 0.0, 0, ""])
        for n, linhas in por_emp.items():
            d0 = linhas[0]
            cat = "Diárias, viagens e adiantamentos" if n in vgm_nums and categoria(d0.get("Natureza", "")) != "Pessoal, encargos e benefícios" else categoria(d0.get("Natureza", ""))
            nome, doc = separa_credor(d0.get("Credor", ""))
            emp = num(d0.get("Valor Empenhado"))
            liq = sum(num(x.get("Valor Liquidado")) for x in linhas)
            pago = sum(num(x.get("Valor Pago")) for x in linhas)
            pags = [[x.get("Data Pagamento", ""), round(num(x.get("Valor Pago")), 2)] for x in linhas if x.get("Data Pagamento")]
            modal = d0.get("Modalidade de Licitação", "") or "Outros"
            e = {"a": ano, "n": n, "p": d0.get("Nro Processo", ""), "c": nome, "doc": doc, "d": d0.get("Descrição do Empenho", "").strip(),
                 "nat": d0.get("Natureza", ""), "cat": cat, "mod": modal, "dt": d0.get("Data Empenho", ""),
                 "emp": round(emp, 2), "liq": round(liq, 2), "pago": round(pago, 2), "pags": pags}
            empenhos.append(e)
            tot["emp"] += emp; tot["pago"] += pago
            cat_v[cat] += emp
            if cat != "Pessoal, encargos e benefícios":
                mod_v[modal][0] += 1; mod_v[modal][1] += emp
                f = forn[(nome, doc)]; f[0] += emp; f[1] += pago; f[2] += 1
        for c in mods.get("CTR", []):
            nome, doc = separa_credor(c.get("Fornecedor", ""))
            contratos.append({"a": ano, "n": c.get("Nro", ""), "t": c.get("Tipo", ""), "f": nome, "doc": doc, "ini": c.get("Data Inicial", ""), "fim": c.get("Data final", ""),
                              "vc": round(num(c.get("Valor Contratado")), 2), "ve": round(num(c.get("Valor Empenhado")), 2), "vp": round(num(c.get("Valor Pago")), 2)})
        por_vgm = defaultdict(list)
        for d in mods.get("VGM", []):
            por_vgm[d.get("Nro Empenho")].append(d)
        for n, linhas in por_vgm.items():
            d0 = linhas[0]
            nome, doc = separa_credor(d0.get("Beneficiário/Responsável", ""))
            diarias.append({"a": ano, "n": n, "b": nome, "d": d0.get("Descrição do Empenho", "").strip(), "dt": d0.get("Data Empenho", ""),
                            "emp": round(num(d0.get("Valor Empenhado")), 2), "pago": round(sum(num(x.get("Valor Pago")) for x in linhas), 2), "nat": d0.get("Natureza", "")})
        anos[ano] = {"empenhado": round(tot["emp"], 2), "pago": round(tot["pago"], 2), "n_empenhos": len(por_emp),
                     "categorias": {k: round(v, 2) for k, v in cat_v.most_common()},
                     "modalidades": {k: [v[0], round(v[1], 2)] for k, v in sorted(mod_v.items(), key=lambda x: -x[1][1])},
                     "fornecedores": [[k[0], k[1], round(v[0], 2), round(v[1], 2), v[2]] for k, v in sorted(forn.items(), key=lambda x: -x[1][0])[:40]],
                     "n_contratos": sum(1 for c in contratos if c["a"] == ano)}
    empenhos.sort(key=lambda e: (e["a"], e["dt"][6:] + e["dt"][3:5] + e["dt"][:2]), reverse=True)
    dados = {"anos": anos, "contratos": contratos, "empenhos": empenhos, "diarias": diarias, "portal": PORTAL + "tdaportalclient.aspx?418"}
    with open(os.path.join(out, "dados", "gastos.json"), "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, separators=(",", ":"))
    return {a: {"empenhado": v["empenhado"], "n_empenhos": v["n_empenhos"], "n_contratos": v["n_contratos"]} for a, v in anos.items()}
