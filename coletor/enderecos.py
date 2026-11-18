"""Extrai rua, bairro e tema de um pedido a partir da ementa oficial.
Regra única, aplicada igual a todos os pedidos.
"""
import re, unicodedata

def sem_acento(s):
    return "".join(c for c in unicodedata.normalize("NFD", s or "") if unicodedata.category(c) != "Mn")

# Bairro canônico -> formas como aparece nas ementas (sem acento, minúsculas)
BAIRROS = {
    "Boqueirão": ["boqueirao"],
    "Guilhermina": ["guilhermina", "vila guilhermina"],
    "Aviação": ["aviacao", "vila aviacao"],
    "Tupi": ["tupi", "vila tupi", "tupy", "vila tupy"],
    "Tupiry": ["tupiry", "jardim tupiry", "tupiri"],
    "Ocian": ["ocian", "cidade ocian", "vila ocian"],
    "Mirim": ["mirim", "vila mirim"],
    "Nova Mirim": ["nova mirim", "vila nova mirim", "jardim nova mirim"],
    "Maracanã": ["maracana", "balneario maracana", "vila maracana"],
    "Caiçara": ["caicara", "vila caicara"],
    "Real": ["real", "jardim real", "vila real", "balneario real"],
    "Flórida": ["florida", "balneario florida", "jardim florida"],
    "Solemar": ["solemar", "jardim solemar", "balneario solemar"],
    "Vila Sônia": ["vila sonia", "sonia"],
    "Quietude": ["quietude", "jardim quietude"],
    "Sítio do Campo": ["sitio do campo"],
    "Ribeirópolis": ["ribeiropolis", "vila ribeiropolis"],
    "Samambaia": ["samambaia", "jardim samambaia"],
    "Esmeralda": ["esmeralda", "balneario esmeralda", "jardim esmeralda"],
    "Melvi": ["melvi", "jardim melvi"],
    "Canto do Forte": ["canto do forte"],
    "Forte": ["forte", "vila do forte"],
    "Anhanguera": ["anhanguera", "jardim anhanguera"],
    "Princesa": ["princesa", "jardim princesa"],
    "Cidade da Criança": ["cidade da crianca"],
    "Tude Bastos": ["tude bastos", "vila tude bastos"],
    "Antártica": ["antartica", "vila antartica"],
    "Parque das Américas": ["parque das americas"],
    "Glória": ["gloria", "jardim gloria"],
    "Vila Assunção": ["vila assuncao", "assuncao"],
    "Imperador": ["imperador", "jardim imperador"],
    "Vila São Jorge": ["vila sao jorge", "sao jorge"],
    "Vilamar": ["vilamar", "vila mar"],
    "Maxland": ["maxland", "balneario maxland"],
    "Trevo": ["trevo", "jardim trevo"],
    "Andaraguá": ["andaragua", "jardim andaragua"],
    "Xixová": ["xixova"],
    "Santa Marina": ["santa marina", "vila santa marina"],
    "Jardim Alice": ["jardim alice"],
    "Vila Atlântica": ["vila atlantica"],
    "Ypiranga": ["ypiranga", "jardim ypiranga", "ipiranga"],
    "Boa Vista": ["boa vista", "vila boa vista"],
    "Militar": ["militar", "balneario militar", "vila militar"],
    "Mirim II": ["mirim ii"],
}
_FORMAS = sorted(((f, b) for b, fs in BAIRROS.items() for f in fs), key=lambda x: -len(x[0]))
_PALAVRA_LOG = r"(?:rua|r\.|avenida|av\.?|travessa|tv\.|alameda|al\.|pra[cç]a|estrada|rodovia|viela|passagem|largo|viaduto)"
RE_RUA = re.compile(
    r"\b(" + _PALAVRA_LOG + r")\s+([A-ZÁÉÍÓÚÂÊÔÃÕÇ0-9][^,;:()\n]*?)"
    r"(?=\s*(?:,|;|:|\(|\)|\.(?:\s|$)|\s[-–—]\s|\bn[º°o]\.?\s*\d|\bn[º°]|\bnº|\bnúmero|\bnumero|\d|\bpr[oó]xim|\baltura|\besquina|\bcom (?:a |o )?(?:rua|av|avenida|travessa|alameda|pra[cç]a)\b|\bentre\b|\bat[eé]\b|\bem frente|\bno bairro|\bbairro|\bna (?:altura|esquina|regi[aã]o|cidade|vila|quadra)|\bno (?:trecho|cruzamento|jardim|balne|munic)|\bnas proximidades|\bjunto\b|\bdo lado|\bao lado|\bperto|\bsentido|\bdesde|\bdo n[º°]|\be\s+(?:rua|av)|\bvila\b|\bjardim\b|\bbalne[aá]rio\b|$))",
    re.I)
TIPO_LOG = {"rua": "Rua", "r.": "Rua", "avenida": "Avenida", "av": "Avenida", "av.": "Avenida", "travessa": "Travessa", "tv.": "Travessa",
            "alameda": "Alameda", "al.": "Alameda", "praça": "Praça", "praca": "Praça", "estrada": "Estrada", "rodovia": "Rodovia",
            "viela": "Viela", "passagem": "Passagem", "largo": "Largo", "viaduto": "Viaduto"}

TEMAS = [  # (tema, padrão) — o primeiro que casar vale
    ("Buraco e asfalto", r"buraco|asfalt|pavimen|recape|tapa[- ]buraco|cascalh|nivelamento d[ao] (?:via|rua|leito)|bloquete|paralelep|rua de terra|via de terra"),
    ("Bueiro, esgoto e alagamento", r"bueiro|boca de lobo|boca-de-lobo|galeria|drenagem|alagament|esgoto|tubula|escoamento|[aá]guas pluviais|caixa de (?:inspe|passagem|gordura)|sarjeta|vala|canal|desobstru|desentup|vazamento|sabesp|\bpv\b"),
    ("Poda e árvores", r"poda|árvore|arvore|galhos?|plantio|arboriza|supress[aã]o|cupim"),
    ("Iluminação", r"ilumina|l[aâ]mpada|poste|luminária|luminaria|\bled\b|reator|escurid"),
    ("Limpeza, mato e entulho", r"limpeza(?! (?:e (?:o )?(?:conserto|desobstru\w*) )?d[aoe]s? (?:bueiro|boca|galeria|caixa|canal|vala|tubula|rede))|entulho|capina|ro[cç]ad|mato|lixo|descarte|terreno baldio|zeladoria|varri[cç]|cata[- ]?(?:treco|bagulho)|res[ií]duo"),
    ("Trânsito e sinalização", r"sinaliza|lombada|redutor|faixa de pedestre|sem[aá]foro|placa|trânsito|transito|estacionamento|tachão|tach[aã]o|setran|velocidade|mão [úu]nica|guia rebaixada|travessia"),
    ("Ônibus e pontos", r"[ôo]nibus|ponto de [ôo]nibus|abrigo|transporte coletivo|linha \d|itiner"),
    ("Pragas e animais", r"desratiza|dedetiza|rato|pragas?|escorpi|dengue|mosquito|nebuliza|animais|cachorro|c[aã]es|zoonose|caramujo"),
    ("Calçadas e acessibilidade", r"cal[cç]ada|acessibilidade|rampa|passeio p[uú]blico|meio[- ]fio|guias?\b"),
    ("Praças, esporte e lazer", r"pra[cç]a|academia|quadra|parque|playground|brinquedo|campo de futebol|pista de skate|lazer|esporte"),
    ("Saúde", r"sa[uú]de|ubs|usafa|upa\b|hospital|m[eé]dic|rem[eé]dio|vacina|atendimento"),
    ("Educação", r"escola|creche|educa[cç]|aluno|professor|ensino"),
    ("Segurança", r"seguran[cç]a|gcm|guarda civil|policia|policiamento|c[aâ]mera|monitoramento|ronda"),
]
_TEMAS_RE = [(t, re.compile(sem_acento(p), re.I)) for t, p in TEMAS]


def temas(ementa):
    """Todos os temas citados no pedido (até 3). Sem tema reconhecido: 'Outros pedidos'."""
    e = sem_acento(ementa or "")
    ts = [t for t, r in _TEMAS_RE if r.search(e)]
    return ts[:3] or ["Outros pedidos"]


def tema(ementa):
    return temas(ementa)[0]


def limpar_rua(tipo, nome):
    nome = re.sub(r"\s+", " ", nome).strip(" .-–—'\"")
    nome = re.sub(r"\s+(?:d[aeo]s?|e|em|no|na)$", "", nome, flags=re.I)
    if len(nome) < 3 or len(nome) > 60 or len(nome.split()) > 8:
        return None
    if re.match(r"(?:p[uú]blica|principal|central|local|de terra|sem nome|projetada|em quest)", nome, re.I):
        return None
    t = TIPO_LOG.get(tipo.lower().rstrip(".") if tipo.lower() not in TIPO_LOG else tipo.lower(), "Rua")
    nome = " ".join(w if w.lower() in {"de", "da", "do", "das", "dos", "e"} or w.isupper() and len(w) <= 3 else w[:1].upper() + w[1:].lower() for w in nome.split())
    return f"{t} {nome}"


def chave_rua(rua):
    """Chave para juntar grafias diferentes da mesma rua."""
    s = sem_acento(rua).lower()
    s = re.sub(r"^(rua|avenida|travessa|alameda|praca|estrada|rodovia|viela|passagem|largo|viaduto) ", r"\1 ", s)
    s = re.sub(r"\b(dr|dra|prof|profa|pres|presidente|doutor|doutora|professor|professora|sen|senador|dep|deputado|gov|governador|pe|padre|cel|coronel|gen|general|eng|engenheiro|ver|vereador|min|ministro|sto|santo|sta|santa|sao|s)\b\.?", "", s)
    s = re.sub(r"\b(de|da|do|das|dos|e)\b", " ", s)
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


ABREV = {"pres": "Presidente", "prof": "Professor", "profa": "Professora", "gov": "Governador", "sen": "Senador", "dep": "Deputado",
          "mal": "Marechal", "gal": "General", "gen": "General", "cel": "Coronel", "eng": "Engenheiro", "min": "Ministro",
          "ver": "Vereador", "cap": "Capitão", "ten": "Tenente", "alm": "Almirante", "sto": "Santo", "sta": "Santa", "pe": "Padre", "cons": "Conselheiro"}


def _normaliza(e):
    e = re.sub(r"\s+", " ", e or "")
    e = re.sub(r"\b(av|r|tv|al)\s*:\s*", lambda m: m.group(1) + ". ", e, flags=re.I)  # "Av: X" -> "Av. X"
    e = re.sub(r"\b(" + "|".join(ABREV) + r")\.\s*(?=[A-ZÁÉÍÓÚ])", lambda m: ABREV[m.group(1).lower()] + " ", e, flags=re.I)
    e = re.sub(r"\b(Dr|Dra|Sr|Sra|St)\.\s*(?=[A-ZÁÉÍÓÚ])", lambda m: m.group(1) + "\u00b7", e)  # protege o ponto
    return e


def extrair(ementa):
    """Retorna (lista_de_ruas, bairro_ou_None)."""
    e = _normaliza(ementa)
    ruas = []
    for m in RE_RUA.finditer(e):
        r = limpar_rua(m.group(1), m.group(2).replace("\u00b7", ". "))
        if r and r not in ruas:
            ruas.append(r)
    # bairro: primeiro o que vem depois da palavra "bairro"; senão, nome conhecido no texto sem as ruas
    base = sem_acento(e).lower()
    bairro = None
    for m in re.finditer(r"\bbairro\s*[:\-–]?\s*(?:d[aeo]\s+)?([a-z ]{3,40})", base):
        trecho = m.group(1)
        for f, b in _FORMAS:
            if trecho.startswith(f) and (len(trecho) == len(f) or not trecho[len(f)].isalpha()):
                bairro = b
                break
        if bairro:
            break
    if not bairro:
        resto = base
        for m in RE_RUA.finditer(sem_acento(e)):
            resto = resto.replace(sem_acento(m.group(0)).lower(), " ")
        for f, b in _FORMAS:
            if len(f) < 5 and f not in ("real", "tupi", "tupy", "forte"):
                continue
            if f in ("real", "forte", "gloria", "princesa", "imperador", "militar", "trevo", "boa vista", "sonia", "sao jorge", "assuncao"):
                pat = r"(?:vila|jardim|balneario|bairro)\s+" + re.escape(f) + r"\b" if f in ("real", "forte", "gloria", "princesa", "imperador", "militar", "trevo", "boa vista", "sonia", "sao jorge", "assuncao") else None
                if f in ("real", "forte", "gloria", "princesa", "imperador", "militar", "trevo", "boa vista") and not re.search(pat, resto):
                    continue
                if f in ("sonia", "sao jorge", "assuncao") and not re.search(r"\b(?:vila\s+)" + re.escape(f) + r"\b", resto):
                    continue
            if re.search(r"(?<![a-z])" + re.escape(f) + r"(?![a-z])", resto):
                bairro = b
                break
    return ruas, bairro
