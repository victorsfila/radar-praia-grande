"""Regra única de classificação das propostas do Radar.
A mesma função é aplicada a todas as propostas de todos os vereadores.
Ela usa só o TIPO oficial do documento e palavras da EMENTA oficial.
"""
import re

GRUPOS = {
    "melhoria": ("Pedidos de melhoria", "Pedidos à Prefeitura: asfalto, poda, iluminação, limpeza, saúde, escola... A Prefeitura não é obrigada a atender."),
    "cobranca": ("Perguntas e cobranças", "Pedidos oficiais de informação ou de providência à Prefeitura e a outros órgãos. Precisam ser aprovados no plenário."),
    "homenagem": ("Homenagens", "Aplausos e parabéns, pesar, títulos de cidadão e medalhas, nomes de rua e datas comemorativas."),
    "lei": ("Propostas de lei", "Projetos que criam ou mudam leis da cidade, a Lei Orgânica ou as regras da Câmara."),
    "outros": ("Outros", "Emendas ao orçamento, moções de apoio ou repúdio, pedidos de audiência pública, vetos e demais documentos."),
}
ORDEM = ["melhoria", "cobranca", "homenagem", "lei", "outros"]

RE = lambda p: re.compile(p, re.I)
PESAR = RE(r"\bpesar\b|condol[eê]n|falecimento|\bluto\b|minuto de sil[eê]ncio|in memoriam")
APLAUSO = RE(r"aplauso|congratula|parab[eé]n|louvor|reconhecimento|homenag|felicita")
TITULO = RE(r"t[ií]tulo (?:de )?(?:\W*cidad|praia)|medalha|honraria|honra ao m[eé]rito|certificado de honra|comenda|diploma|homenag")
NOME_RUA = RE(r"\bdenomina|\bd[aá] (?:o )?nome\b")
DATA = RE(r"institui (?:o|a) (?:dia|semana|m[eê]s|data)|\bdia municipal\b|semana municipal|calend[aá]rio oficial|data comemorativa")
POSICAO = RE(r"rep[uú]dio|apelo|\bapoio\b|protesto|solidariedade a|manifesta")

LEI_TIPOS = {"Projeto de Lei", "Projeto de Lei Complementar", "Proposta de Emenda à L.O.", "Projeto de Resolução"}
DL_TIPOS = {"Projeto de Decreto Legislativo", "Decreto Legislativo"}


def classificar(tipo, ementa):
    """Retorna (grupo, subgrupo). Regras aplicadas nesta ordem:"""
    e = ementa or ""
    # 1. Homenagens, em qualquer tipo de documento em que apareçam
    if tipo == "Moção":
        if POSICAO.search(e) and not APLAUSO.search(e):
            return "outros", "Moção de apoio, apelo ou repúdio"
        return "homenagem", ("Pesar" if PESAR.search(e) else "Aplauso e parabéns")
    if tipo in DL_TIPOS and TITULO.search(e):
        return "homenagem", "Título de cidadão e medalha"
    if tipo in LEI_TIPOS and NOME_RUA.search(e):
        return "homenagem", "Nome de rua, praça ou prédio"
    if tipo in LEI_TIPOS and DATA.search(e):
        return "homenagem", "Data comemorativa"
    if tipo == "Requerimento" and PESAR.search(e):
        return "homenagem", "Pesar"
    # 2. Tipos principais
    if tipo == "Indicações":
        return "melhoria", ""
    if tipo == "Requerimento":
        return "cobranca", ""
    if tipo in LEI_TIPOS:
        return "lei", ""
    # 3. Todo o resto
    if tipo.startswith("Emenda"):
        return "outros", "Emenda ao orçamento"
    return "outros", tipo


REGRA_TEXTO = [
    "Moção: vira Homenagem (aplauso, parabéns ou pesar). Exceção: moção de apoio, apelo ou repúdio, que vai para Outros.",
    "Decreto legislativo que dá título de cidadão, medalha ou honraria: Homenagem.",
    "Projeto de lei que dá nome a rua, praça ou prédio, ou que cria data comemorativa (dia, semana ou mês de algo): Homenagem.",
    "Requerimento de voto de pesar ou minuto de silêncio: Homenagem.",
    "Toda Indicação que sobrou: Pedido de melhoria.",
    "Todo Requerimento que sobrou: Pergunta ou cobrança.",
    "Projeto de lei, lei complementar, emenda à Lei Orgânica e projeto de resolução que sobraram: Proposta de lei.",
    "Todo o resto (emendas ao orçamento, pedidos de audiência pública, outros decretos legislativos, vetos): Outros.",
]
