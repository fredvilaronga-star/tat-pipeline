#!/usr/bin/env python3
"""
Migração ÚNICA: popula as bases Notion "Contatos" e "Eventos" a partir dos
arquivos data_contatos.json e data_eventos.json. Roda no GitHub Actions
(usa NOTION_TOKEN). É idempotente: se a base já tiver linhas, pula.

Depois de rodar uma vez, você edita contatos/eventos direto no Notion e o
dashboard reflete (o generate_dashboard.py passa a ler do Notion).
"""
import os, sys, json, time, urllib.request

TOKEN = os.environ["NOTION_TOKEN"]
CONTAS_DS   = os.environ.get("CONTAS_DS", "77949769-ec49-45d5-95fa-111f6f9d64a1")
CONTATOS_DS = os.environ.get("CONTATOS_DS", "af10b604-ea2b-4444-8348-40559259a7e2")
EVENTOS_DS  = os.environ.get("EVENTOS_DS", "7b0f80d1-2075-4e3c-adeb-f7e28c2c2603")
V = "2025-09-03"; API = "https://api.notion.com/v1"

def req(url, payload, method="POST"):
    r = urllib.request.Request(url, data=json.dumps(payload).encode(), method=method, headers={
        "Authorization": f"Bearer {TOKEN}", "Notion-Version": V, "Content-Type": "application/json"})
    with urllib.request.urlopen(r, timeout=60) as resp:
        return json.loads(resp.read().decode())

def count(ds):
    j = req(f"{API}/data_sources/{ds}/query", {"page_size": 1})
    return len(j.get("results", []))

def query_all(ds):
    out, cur = [], None
    while True:
        p = {"page_size": 100}
        if cur: p["start_cursor"] = cur
        j = req(f"{API}/data_sources/{ds}/query", p)
        out += j.get("results", [])
        if not j.get("has_more"): break
        cur = j["next_cursor"]
    return out

def title_of(pg, n="Conta"):
    return "".join(t.get("plain_text","") for t in (pg.get("properties",{}).get(n,{}).get("title") or []))

def rt(s):   return {"rich_text":[{"text":{"content": str(s)[:1900]}}]} if s else {"rich_text":[]}
def tt(s):   return {"title":[{"text":{"content": str(s)[:1900] or "—"}}]}
def se(s):   return {"select":{"name": str(s)}} if s else {"select": None}
def nu(x):
    try: return {"number": float(str(x).replace(",","."))}
    except: return {"number": None}
def da(s):   return {"date":{"start": s}} if s else {"date": None}
def rel(i):  return {"relation":[{"id": i}]} if i else {"relation": []}

def create(ds, props):
    req(f"{API}/pages", {"parent":{"type":"data_source_id","data_source_id": ds}, "properties": props})

def main():
    # mapa empresa -> conta page id
    name2id = {}
    for pg in query_all(CONTAS_DS):
        name2id[title_of(pg,"Conta")] = pg["id"]

    # --- CONTATOS ---
    if count(CONTATOS_DS) > 0:
        print("Contatos já populado — pulando.")
    else:
        contatos = json.load(open("data_contatos.json", encoding="utf-8"))
        for c in contatos:
            props = {
                "Nome": tt(c.get("nome")),
                "Empresa": rel(name2id.get(c.get("empresa"))),
                "Cargo": rt(c.get("cargo")),
                "Área": se(c.get("area") if c.get("area") in
                    ["Finance","CEO","Operations","Flight Ops","Sustainability","Strategy","Procurement"] else "Outros"),
                "Importância": se(c.get("imp")),
                "Influência": nu(c.get("infl")),
                "Acessibilidade": nu(c.get("acess")),
                "Sponsor WaterLine": se(c.get("sponsor") if c.get("sponsor") in ["Sim","Não"] else None),
                "Champion": se(c.get("champion") if c.get("champion") in ["Sim","Não"] else None),
                "Canal de acesso": rt(c.get("canal")),
                "Conector nomeado": rt(c.get("conector")),
                "Fonte": rt(c.get("fonte") or "Matriz de Acesso v6"),
                "Email / Domínio": rt(c.get("email")),
                "Próxima ação": rt(c.get("proxima")),
            }
            create(CONTATOS_DS, props); time.sleep(0.34)
        print(f"Contatos migrados: {len(contatos)}")

    # --- EVENTOS ---
    if count(EVENTOS_DS) > 0:
        print("Eventos já populado — pulando.")
    else:
        eventos = json.load(open("data_eventos.json", encoding="utf-8"))
        for e in eventos:
            props = {
                "Evento": tt(e.get("evento")),
                "Organizador": rt(e.get("org")),
                "Categoria": rt(e.get("cat")),
                "Início": da(e.get("ini")),
                "Fim": da(e.get("fim")),
                "Cidade": rt(e.get("cidade")),
                "País": rt(e.get("pais")),
                "Importância": se(e.get("imp")),
                "Participação": se(e.get("participacao") or "A decidir"),
                "Inscrição até": da(e.get("inscricao")),
                "Contas-alvo": rt(e.get("alvo")),
                "Decisores": rt(e.get("decisores")),
                "Recomendação": rt(e.get("rec")),
                "Score": nu(e.get("score")),
                "Fonte": rt("Calendário de Eventos (Access Intelligence v6)"),
            }
            create(EVENTOS_DS, props); time.sleep(0.34)
        print(f"Eventos migrados: {len(eventos)}")

if __name__ == "__main__":
    main()
