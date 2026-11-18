#!/usr/bin/env python3
"""Confere se uma coleta nova está completa antes de publicar.
Se algo parecer errado, sai com erro e o robô NÃO publica: o site fica com a última versão boa.
Uso: python3 conferir.py coleta_nova.json site/dados/resumo.json
"""
import json, sys

def falha(msg):
    print("COLETA REJEITADA:", msg)
    sys.exit(1)

novo = json.load(open(sys.argv[1], encoding="utf-8"))
try:
    antigo = json.load(open(sys.argv[2], encoding="utf-8"))["meta"]
except Exception:
    antigo = {}

P, S, M = novo.get("parlamentares", []), novo.get("sessoes", []), novo.get("materias", [])
if len(P) < 20:
    falha(f"só {len(P)} vereadores (esperado 20 ou mais)")
# todas as propostas que o sistema anunciou foram baixadas?
for k, v in novo.items():
    if k.startswith("total") and k[5:].isdigit():
        ano = k[5:]
        n = len({m["c"] for m in M if m.get("t", "").endswith("/" + ano)})
        if n < v * 0.995:
            falha(f"propostas de {ano}: baixadas {n} de {v}")
if antigo.get("total_props") and len({m["c"] for m in M}) < antigo["total_props"] * 0.98:
    falha(f"propostas caíram de {antigo['total_props']} para {len(M)}")
if antigo.get("n_sessoes") and len(S) < antigo["n_sessoes"] - 2:
    falha(f"sessões caíram de {antigo['n_sessoes']} para {len(S)}")
com_pres = sum(1 for s in S if "Presentes" in s.get("presTxt", "") and "Sem presen" not in s.get("presTxt", ""))
if antigo.get("n_sessoes_reg") and com_pres < antigo["n_sessoes_reg"] - 2:
    falha(f"sessões com presença caíram de {antigo['n_sessoes_reg']} para {com_pres}")
n_vot = sum(len(s.get("votacoes", [])) for s in S)
if antigo.get("n_votacoes") and n_vot < antigo["n_votacoes"] * 0.95:
    falha(f"votações caíram de {antigo['n_votacoes']} para {n_vot}")
G = novo.get("gastos", {})
for ano, mods in G.items():
    if not mods.get("DSP"):
        falha(f"despesas de {ano} vieram vazias")
ant_g = antigo.get("gastos") or {}
for ano, v in ant_g.items():
    novos = len({d.get("Nro Empenho") for d in G.get(ano, {}).get("DSP", [])})
    if novos < v.get("n_empenhos", 0) * 0.98:
        falha(f"empenhos de {ano} caíram de {v['n_empenhos']} para {novos}")
sem_texto = sum(1 for m in M if not m.get("ementa"))
if sem_texto > len(M) * 0.05:
    falha(f"{sem_texto} propostas sem ementa: a página da Câmara pode ter mudado")
print(f"Coleta OK: {len(P)} vereadores, {len(S)} sessões ({com_pres} com presença), {len(M)} propostas.")
