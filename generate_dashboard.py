#!/usr/bin/env python3
"""
TAT WaterLine — Gerador do dashboard PÚBLICO (board Kanban clicável, identidade TAT).

Lê Contas + Interações do Notion (API oficial) e gera um index.html com o funil
completo: cards das companhias por estágio, clicáveis, com a TIMELINE completa das
interações (datas, tipo, com quem falamos). Identidade visual TAT WaterLine
(navy + dourado). Mostra nomes de conta, estágios e histórico; NÃO expõe valores (US$).

Env (GitHub Secrets): NOTION_TOKEN, CONTAS_DS, INTERACOES_DS
"""
import os, sys, json, datetime, urllib.request

NOTION_TOKEN  = os.environ.get("NOTION_TOKEN", "")
CONTAS_DS     = os.environ.get("CONTAS_DS", "77949769-ec49-45d5-95fa-111f6f9d64a1")
INTERACOES_DS = os.environ.get("INTERACOES_DS", "54d6bc50-22b3-4c9a-9eb9-6a492224bbf8")
CONTATOS_DS = os.environ.get("CONTATOS_DS", "af10b604-ea2b-4444-8348-40559259a7e2")
EVENTOS_DS  = os.environ.get("EVENTOS_DS", "7b0f80d1-2075-4e3c-adeb-f7e28c2c2603")
NOTION_VERSION = "2025-09-03"
API = "https://api.notion.com/v1"

STAGE_ORDER = ["Alvo","Contato","Reunião","Diagnóstico","Comitê","Mandato","Implantação"]
STAGE_COLOR = {"Alvo":"#7c8ba0","Contato":"#6f92b8","Reunião":"#3fb6a8","Diagnóstico":"#9b7fe0",
               "Comitê":"#c9a24a","Mandato":"#3fb37f","Implantação":"#2ec38a"}
QUAD_COLOR = {"Executar agora":"#3fb37f","Converter":"#6f92b8","Construir acesso":"#9b7fe0",
              "Cultivar":"#c9a24a","Observar":"#7c8ba0"}
TYPE_COLOR = {"Email":"#6f92b8","WhatsApp":"#3fb37f","Reunião":"#3fb6a8","Diagnóstico":"#9b7fe0",
              "One-pager":"#c9a24a","Nota":"#7c8ba0","Ligação":"#6f92b8"}
FLAG = {"Brasil":"🇧🇷","EAU":"🇦🇪","Panamá":"🇵🇦","EUA":"🇺🇸","Canadá":"🇨🇦","Catar":"🇶🇦",
        "Chile":"🇨🇱","Índia":"🇮🇳","Irlanda":"🇮🇪","Coreia do Sul":"🇰🇷","Turquia":"🇹🇷",
        "Japão":"🇯🇵","Etiópia":"🇪🇹","Angola":"🇦🇴","Portugal":"🇵🇹"}

def _req(url, payload):
    data = json.dumps(payload).encode()
    r = urllib.request.Request(url, data=data, method="POST", headers={
        "Authorization": f"Bearer {NOTION_TOKEN}", "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json"})
    with urllib.request.urlopen(r, timeout=60) as resp:
        return json.loads(resp.read().decode())

def query_all(ds_id):
    out, cursor = [], None
    while True:
        payload = {"page_size": 100}
        if cursor: payload["start_cursor"] = cursor
        j = _req(f"{API}/data_sources/{ds_id}/query", payload)
        out.extend(j.get("results", []))
        if not j.get("has_more"): break
        cursor = j.get("next_cursor")
    return out

def P(pg, n): return pg.get("properties", {}).get(n, {}) or {}
def sel(pg, n):
    s = P(pg, n).get("select");  return s.get("name") if s else None
def num(pg, n): return P(pg, n).get("number")
def dstart(pg, n):
    d = P(pg, n).get("date");    return d.get("start") if d else None
def rtext(pg, n):
    return "".join(t.get("plain_text","") for t in P(pg, n).get("rich_text", []) or [])
def title(pg, n):
    return "".join(t.get("plain_text","") for t in (P(pg, n).get("title") or []))
def relids(pg, n):
    return [r.get("id") for r in P(pg, n).get("relation", []) or []]
def to_date(s):
    if not s: return None
    try: return datetime.date.fromisoformat(s[:10])
    except Exception: return None

def main():
    if not NOTION_TOKEN:
        print("ERRO: defina NOTION_TOKEN", file=sys.stderr); sys.exit(1)
    today = datetime.date.today()
    contas = query_all(CONTAS_DS)
    inter  = query_all(INTERACOES_DS)

    tmap, imap = {}, {}
    for it in inter:
        ds = dstart(it, "Data"); d = to_date(ds)
        ev = {"d": ds[:10] if ds else None, "t": sel(it,"Tipo") or "Nota",
              "titulo": title(it,"Interação"), "desc": rtext(it,"Descrição"),
              "resp": rtext(it,"Responsável")}
        for aid in relids(it, "Conta"):
            e = tmap.setdefault(aid, {"n":0,"last":None}); e["n"]+=1
            if d and (e["last"] is None or d > e["last"]): e["last"] = d
            imap.setdefault(aid, []).append(ev)
    for aid in imap:
        imap[aid].sort(key=lambda x: (x["d"] or ""), reverse=True)

    accts = []
    for p in contas:
        t = tmap.get(p.get("id"), {"n":0,"last":None})
        prazo = to_date(dstart(p, "Prazo"))
        accts.append({
            "nome": title(p,"Conta"), "pais": sel(p,"País"),
            "estagio": sel(p,"Estágio") or "Alvo", "quad": sel(p,"Quadrante"),
            "score": num(p,"Opportunity Score"), "fleet": num(p,"Frota Boeing"),
            "prop": num(p,"Propensão"), "prazo": prazo.isoformat() if prazo else None,
            "sponsor": rtext(p,"Sponsor-alvo"), "caminho": rtext(p,"Caminho de acesso"),
            "proxima": rtext(p,"Próxima ação"), "risco": rtext(p,"Risco / objeção"),
            "toques": t["n"], "ult": t["last"].isoformat() if t["last"] else None,
            "eventos": imap.get(p.get("id"), []),
        })

    total = len(accts)
    em_pipeline = sum(1 for a in accts if a["estagio"] != "Alvo")
    diag_plus = sum(1 for a in accts if a["estagio"] in ("Diagnóstico","Comitê","Mandato","Implantação"))
    fleet = sum(int(a["fleet"] or 0) for a in accts)
    def pdelta(a):
        d = to_date(a["prazo"]);  return (d - today).days if d else None
    venc  = sum(1 for a in accts if pdelta(a) is not None and 0 <= pdelta(a) <= 7)
    venc0 = sum(1 for a in accts if pdelta(a) is not None and pdelta(a) < 0 and a["estagio"] != "Alvo")

    def _load(fn):
        try: return json.load(open(fn, encoding="utf-8"))
        except Exception: return []
    id2name = {p.get("id"): title(p,"Conta") for p in contas}
    # Contatos: lê do Notion; se vazio, cai no JSON semente
    contatos = []
    try:
        for pg in query_all(CONTATOS_DS):
            cargo = rtext(pg,"Cargo"); status = rtext(pg,"Status")
            emp = relids(pg,"Empresa")
            contatos.append({"nome": title(pg,"Nome"),
                "empresa": id2name.get(emp[0]) if emp else "",
                "cargo": cargo, "area": sel(pg,"Área") or "Outros",
                "infl": num(pg,"Influência"), "acess": num(pg,"Acessibilidade"),
                "canal": rtext(pg,"Canal de acesso"), "conector": rtext(pg,"Conector nomeado"),
                "sponsor": sel(pg,"Sponsor WaterLine"), "champion": sel(pg,"Champion"),
                "email": rtext(pg,"Email / Domínio"), "proxima": rtext(pg,"Próxima ação"),
                "imp": sel(pg,"Importância") or "Baixa",
                "morto": ("APOSENTAD" in cargo.upper() or "MORTO" in status.upper())})
    except Exception: contatos = []
    if not contatos: contatos = _load("data_contatos.json")
    order = {"Alta":0,"Média":1,"Baixa":2}
    contatos.sort(key=lambda c: (order.get(c.get("imp"),3), c.get("empresa") or ""))
    # Eventos: lê do Notion; se vazio, cai no JSON semente
    eventos = []
    try:
        for pg in query_all(EVENTOS_DS):
            eventos.append({"evento": title(pg,"Evento"), "org": rtext(pg,"Organizador"),
                "cat": rtext(pg,"Categoria"), "ini": dstart(pg,"Início"), "fim": dstart(pg,"Fim"),
                "cidade": rtext(pg,"Cidade"), "pais": rtext(pg,"País"),
                "imp": sel(pg,"Importância") or "Média", "participacao": sel(pg,"Participação") or "A decidir",
                "inscricao": dstart(pg,"Inscrição até"), "alvo": rtext(pg,"Contas-alvo"),
                "decisores": rtext(pg,"Decisores"), "rec": rtext(pg,"Recomendação"), "score": num(pg,"Score")})
    except Exception: eventos = []
    if not eventos: eventos = _load("data_eventos.json")
    html = render(today, accts, total, em_pipeline, diag_plus, fleet, venc, venc0, len(inter), contatos, eventos)
    with open("index.html","w",encoding="utf-8") as f:
        f.write(html)
    print(f"OK · {total} contas · {len(inter)} interações · {venc} prazos ≤7d · {venc0} vencidos")

def _e(s):
    return (str(s) if s is not None else "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")

def render(today, accts, total, em_pipeline, diag_plus, fleet, venc, venc0, n_inter, contatos=None, eventos=None):
    d_str = today.strftime("%d/%m/%Y")
    for i, a in enumerate(accts): a["_i"] = i
    DATA = json.dumps(accts, ensure_ascii=False)
    cols = ""
    for s in STAGE_ORDER:
        items = [a for a in accts if a["estagio"] == s]
        items.sort(key=lambda a: (a["score"] is None, -(a["score"] or 0)))
        body = "".join(
            f'<div class="card" style="border-left-color:{STAGE_COLOR[s]}" onclick="openD({a["_i"]})" id="c{a["_i"]}"></div>'
            for a in items) or '<div class="empty">—</div>'
        cols += f'<div class="col"><div class="col-h"><span class="dot" style="background:{STAGE_COLOR[s]}"></span>{s}<span class="col-n">{len(items)}</span></div>{body}</div>'
    contatos = contatos or []; eventos = eventos or []
    IMPC = {"Alta":"#e2687e","Média":"#c9a24a","Baixa":"#7c8ba0"}
    crows = ""
    for imp in ["Alta","Média","Baixa"]:
        grp = [c for c in contatos if c.get("imp")==imp]
        if not grp: continue
        crows += f'<tr class="grp"><td colspan="7"><span class="dot" style="background:{IMPC[imp]}"></span> Importância {imp} · {len(grp)}</td></tr>'
        for c in grp:
            morto = c.get("morto")
            spon = '<span class="tag tg">Sponsor</span>' if c.get("sponsor")=="Sim" else ''
            champ = '<span class="tag tb">Champion</span>' if c.get("champion")=="Sim" else ''
            nome = f'<s>{_e(c.get("nome"))}</s> <span class="tag tm">lead morto</span>' if morto else f'<b>{_e(c.get("nome"))}</b>'
            crows += ('<tr>'
                f'<td>{nome}</td><td>{_e(c.get("empresa"))}</td>'
                f'<td>{_e((c.get("cargo") or "")[:60])}</td><td>{_e(c.get("area"))}</td>'
                f'<td class="num">{_e(c.get("infl"))}/{_e(c.get("acess"))}</td>'
                f'<td>{spon}{champ}</td>'
                f'<td class="sm">{_e((c.get("canal") or c.get("conector") or "")[:60])}</td></tr>')
    contatos_html = f'<table class="ctab"><thead><tr><th>Nome</th><th>Empresa</th><th>Cargo</th><th>Área</th><th>Infl/Acess</th><th>Flags</th><th>Canal de acesso</th></tr></thead><tbody>{crows}</tbody></table>'

    def _evd(s):
        if not s: return "—"
        p=s.split("-"); return f"{p[2]}/{p[1]}" if len(p)==3 else s
    today_iso = today.strftime("%Y-%m-%d")
    def _ekey(e): return e.get("ini") or "9999-99-99"
    def _past(e):
        f = e.get("fim") or e.get("ini")
        return bool(f) and f < today_iso
    futuros = sorted([e for e in eventos if not _past(e)], key=_ekey)
    passados = sorted([e for e in eventos if _past(e)], key=_ekey, reverse=True)
    def _ecard(e, past=False):
        ic = IMPC.get(e.get("imp"),"#7c8ba0")
        part = e.get("participacao") or "A decidir"
        pc = "#3fb37f" if part=="Confirmado" else "#c9a24a" if part=="Avaliar" else "#7c8ba0"
        # dias até a inscrição / evento
        badge = ""
        ins_iso = e.get("inscricao")
        if not past and ins_iso and ins_iso >= today_iso:
            try:
                di = (to_date(ins_iso) - today).days
                if di <= 30:
                    bc = "#e2687e" if di <= 7 else "#c9a24a"
                    badge = f'<span class="ev-cd" style="color:{bc};border-color:{bc}66">inscrição em {di}d</span>'
            except Exception: pass
        ins = f'<span class="ev-ins">Inscrição: {_evd(ins_iso)}</span>' if ins_iso else '<span class="ev-ins tofill">Inscrição: definir</span>'
        cls = "ecard pastev" if past else "ecard"
        return ('<div class="'+cls+'" style="border-left-color:'+ic+'">'
            f'<div class="ec-top"><div class="ec-name">{_e(e.get("evento"))}</div>'
            f'<span class="tag" style="color:{ic};border-color:{ic}66">{e.get("imp")}</span></div>'
            f'<div class="ec-when">📅 {_evd(e.get("ini"))}–{_evd(e.get("fim"))} · {_e(e.get("cidade"))}, {_e(e.get("pais"))} · {_e(e.get("org"))}</div>'
            f'<div class="ec-row"><span class="tag" style="color:{pc};border-color:{pc}66">{part}</span> {ins}{badge}</div>'
            f'<div class="ec-alvo"><b>Contas-alvo:</b> {_e(e.get("alvo"))}</div>'
            f'<div class="ec-rec">{_e(e.get("rec"))}</div></div>')
    ecards = "".join(_ecard(e) for e in futuros)
    if passados:
        ecards += '<div class="ev-div">Já realizados</div>'
        ecards += "".join(_ecard(e, past=True) for e in passados)
    eventos_html = f'<div class="egrid">{ecards}</div>' if ecards else '<div class="empty">Sem eventos.</div>'

    return f'''<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>TAT WaterLine · Pipeline</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');
*{{box-sizing:border-box;margin:0;padding:0}}
:root{{--navy:#0a1a2e;--navy1:#0c2038;--navy2:#102844;--line:#1b3654;--line2:#152a44;
--gold:#c9a24a;--gold2:#e0bd6a;--steel:#6f92b8;--white:#eaf2fb;--mut:#8399b4;--rd:#e2687e;--grn:#3fb37f;
--fn:'Inter',system-ui,-apple-system,sans-serif}}
body{{background:var(--navy);color:var(--white);font-family:var(--fn);font-size:13px;line-height:1.5;padding-bottom:40px}}
/* ---- header / brand ---- */
.hdr{{background:linear-gradient(160deg,#091729,#0e2542);border-bottom:1px solid var(--line);padding:22px 30px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:16px;position:relative;overflow:hidden}}
.brand{{position:relative;z-index:2}}
.b-op{{font-size:12px;font-weight:600;letter-spacing:7px;color:var(--white);opacity:.92}}
.b-wl{{font-size:30px;font-weight:800;letter-spacing:6px;line-height:1;margin-top:2px}}
.b-wl .g{{color:var(--gold)}}
.swoosh{{display:block;margin:5px 0 5px;opacity:.95}}
.b-tag{{font-size:11px;font-weight:600;letter-spacing:1.5px;color:var(--white)}}
.b-tag .g{{color:var(--gold)}}
.hr{{text-align:right;position:relative;z-index:2}}
.hr .u{{font-size:12px;font-weight:800;color:var(--gold)}}
.hr .s{{font-size:10px;color:var(--mut);text-transform:uppercase;letter-spacing:.6px;margin-top:4px}}
/* ---- kpis ---- */
.kpis{{display:flex;gap:11px;padding:18px 30px;flex-wrap:wrap;border-bottom:1px solid var(--line2)}}
.kpi{{background:var(--navy1);border:1px solid var(--line);border-radius:11px;padding:12px 17px;min-width:110px;position:relative;overflow:hidden}}
.kpi::before{{content:'';position:absolute;top:0;left:0;right:0;height:2px;background:var(--steel)}}
.kpi.g::before{{background:var(--gold)}}.kpi.grn::before{{background:var(--grn)}}.kpi.rd::before{{background:var(--rd)}}
.kpi .v{{font-size:23px;font-weight:900;letter-spacing:-.5px;line-height:1}}
.kpi.g .v{{color:var(--gold)}}.kpi.grn .v{{color:var(--grn)}}.kpi.rd .v{{color:var(--rd)}}
.kpi .l{{font-size:9.5px;color:var(--mut);text-transform:uppercase;letter-spacing:.5px;margin-top:6px}}
/* ---- board ---- */
.board{{display:flex;gap:9px;padding:18px 22px;align-items:flex-start}}
.col{{flex:1 1 0;min-width:0;background:var(--navy1);border:1px solid var(--line2);border-radius:12px;padding:9px}}
@media(max-width:900px){{.board{{overflow-x:auto}}.col{{flex:0 0 210px}}}}
.col-h{{display:flex;align-items:center;gap:7px;font-size:10.5px;font-weight:800;text-transform:uppercase;letter-spacing:.5px;color:var(--mut);margin-bottom:11px;padding:0 2px}}
.dot{{width:8px;height:8px;border-radius:50%}}
.col-n{{margin-left:auto;background:var(--navy2);border:1px solid var(--line);border-radius:20px;padding:1px 8px;font-size:10px;color:var(--mut)}}
.card{{background:var(--navy2);border:1px solid var(--line);border-left:3px solid var(--steel);border-radius:10px;padding:11px;margin-bottom:9px;cursor:pointer;transition:.15s}}
.card:hover{{border-color:var(--gold);box-shadow:0 4px 16px rgba(0,0,0,.35);transform:translateY(-1px)}}
.c-top{{display:flex;justify-content:space-between;align-items:flex-start;gap:6px}}
.c-name{{font-size:13px;font-weight:800;line-height:1.2}}.c-flag{{font-size:14px}}
.chips{{display:flex;gap:5px;flex-wrap:wrap;margin:7px 0 5px}}
.chip{{font-size:8.5px;font-weight:700;padding:2px 7px;border-radius:20px;border:1px solid;letter-spacing:.3px;white-space:nowrap}}
.chip.mut{{border-color:var(--line);color:var(--mut)}}
.c-meta{{font-size:10px;color:var(--mut)}}
.pz{{display:inline-block;font-size:9.5px;font-weight:700;color:var(--mut);border:1px solid var(--line);border-radius:5px;padding:2px 7px;margin-top:6px}}
.pz-a{{color:#20160a;background:var(--gold);border-color:var(--gold)}}
.pz-r{{color:#fff;background:var(--rd);border-color:var(--rd)}}
.empty{{font-size:10px;color:var(--mut);text-align:center;padding:14px 0;opacity:.6}}
.ftr{{text-align:center;color:var(--mut);font-size:10.5px;margin-top:14px;padding:0 30px;line-height:1.7}}
.ftr b{{color:var(--gold)}}
/* ---- tabs ---- */
.tabs{{display:flex;gap:4px;padding:14px 22px 0;border-bottom:1px solid var(--line2)}}
.tabx{{padding:10px 18px;font-size:13px;font-weight:700;color:var(--mut);cursor:pointer;border-bottom:3px solid transparent;transition:.15s;display:flex;align-items:center;gap:7px}}
.tabx:hover{{color:var(--white)}}
.tabx.on{{color:var(--gold);border-bottom-color:var(--gold)}}
.tct{{background:var(--navy2);border:1px solid var(--line);border-radius:20px;padding:0 8px;font-size:10px;color:var(--mut)}}
.panel{{display:none}}.panel.on{{display:block}}
.wrap{{max-width:1200px;margin:0 auto;padding:20px 22px}}
/* ---- contatos table ---- */
.ctab{{width:100%;border-collapse:collapse;font-size:12px}}
.ctab th{{text-align:left;font-size:9.5px;text-transform:uppercase;letter-spacing:.5px;color:var(--mut);padding:8px 10px;border-bottom:1px solid var(--line);font-weight:700}}
.ctab td{{padding:8px 10px;border-bottom:1px solid var(--line2);vertical-align:top}}
.ctab tr.grp td{{background:var(--navy1);font-size:10.5px;font-weight:800;text-transform:uppercase;letter-spacing:.5px;color:var(--white);padding:9px 10px}}
.ctab tr.grp .dot{{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:6px}}
.ctab td.num{{font-variant-numeric:tabular-nums;color:var(--mut)}}
.ctab td.sm{{font-size:10.5px;color:var(--mut)}}
.ctab s{{color:var(--mut)}}
.tag{{display:inline-block;font-size:8.5px;font-weight:700;padding:1px 6px;border-radius:10px;border:1px solid var(--line);margin-right:4px;white-space:nowrap}}
.tag.tg{{color:var(--grn);border-color:#3fb37f55}}.tag.tb{{color:var(--steel);border-color:#6f92b855}}.tag.tm{{color:var(--rd);border-color:#e2687e55}}
/* ---- eventos ---- */
.egrid{{display:grid;grid-template-columns:repeat(2,1fr);gap:14px}}
@media(max-width:820px){{.egrid{{grid-template-columns:1fr}}}}
.ecard{{background:var(--navy1);border:1px solid var(--line);border-left:3px solid var(--gold);border-radius:11px;padding:14px 16px}}
.ec-top{{display:flex;justify-content:space-between;align-items:flex-start;gap:8px}}
.ec-name{{font-size:14px;font-weight:800;line-height:1.25}}
.ec-when{{font-size:11px;color:var(--mut);margin:8px 0 8px}}
.ec-row{{display:flex;align-items:center;gap:6px;margin-bottom:9px}}
.ev-ins{{font-size:10px;font-weight:700;color:var(--gold2)}}
.ev-ins.tofill{{color:var(--mut)}}
.ec-alvo{{font-size:11px;color:var(--white);margin-bottom:6px}}.ec-alvo b{{color:var(--mut);font-weight:700}}
.ec-rec{{font-size:11px;color:var(--mut);line-height:1.5;border-top:1px solid var(--line2);padding-top:7px}}
.pastev{{opacity:.45}}
.ev-cd{{font-size:9.5px;font-weight:800;text-transform:uppercase;letter-spacing:.4px;border:1px solid;border-radius:5px;padding:1px 6px;margin-left:auto}}
.ev-div{{grid-column:1/-1;font-size:10px;font-weight:800;text-transform:uppercase;letter-spacing:1.5px;color:var(--mut);border-top:1px solid var(--line);padding-top:12px;margin-top:4px}}
/* ---- drawer ---- */
.ov{{position:fixed;inset:0;background:rgba(3,9,18,.62);opacity:0;pointer-events:none;transition:.2s;z-index:90}}
.ov.on{{opacity:1;pointer-events:auto}}
.drw{{position:fixed;top:0;right:0;bottom:0;width:min(470px,95vw);background:var(--navy1);border-left:1px solid var(--line);transform:translateX(100%);transition:.25s;z-index:100;overflow-y:auto;box-shadow:-16px 0 50px rgba(0,0,0,.55)}}
.drw.on{{transform:translateX(0)}}
.drw-h{{padding:20px 24px;border-bottom:1px solid var(--line);background:linear-gradient(160deg,#0b1e37,#123059);position:sticky;top:0;z-index:2}}
.drw-x{{position:absolute;top:17px;right:18px;background:var(--navy2);border:1px solid var(--line);color:var(--mut);width:30px;height:30px;border-radius:8px;cursor:pointer;font-size:15px}}
.drw-x:hover{{color:#fff;border-color:var(--gold)}}
.drw-c{{font-size:21px;font-weight:800}}.drw-s{{font-size:11px;color:var(--mut);margin-top:3px}}
.drw-b{{padding:18px 24px}}
.g2{{display:grid;grid-template-columns:1fr 1fr;gap:9px;margin-bottom:12px}}
.f{{background:var(--navy2);border:1px solid var(--line);border-radius:9px;padding:9px 12px}}
.f .l{{font-size:9px;color:var(--mut);text-transform:uppercase;letter-spacing:.5px}}.f .v{{font-size:13px;font-weight:700;margin-top:3px}}
.f.wide{{grid-column:1/3}}
.risco{{font-size:11px;color:var(--gold2);background:rgba(201,162,74,.08);border:1px solid rgba(201,162,74,.28);border-radius:9px;padding:10px 12px;line-height:1.5;margin-top:2px}}
.sec{{font-size:11px;font-weight:800;text-transform:uppercase;letter-spacing:.6px;color:var(--gold);margin:18px 0 12px;display:flex;align-items:center;gap:9px}}
.sec::after{{content:'';flex:1;height:1px;background:var(--line)}}
.tlw{{position:relative;padding-left:17px}}
.tlw::before{{content:'';position:absolute;left:4px;top:5px;bottom:5px;width:2px;background:var(--line)}}
.ev{{position:relative;margin-bottom:14px}}
.ev::before{{content:'';position:absolute;left:-15px;top:3px;width:9px;height:9px;border-radius:50%;background:var(--gold);border:2px solid var(--navy1)}}
.ev-d{{font-size:9.5px;color:var(--mut);font-weight:700;text-transform:uppercase;letter-spacing:.4px}}
.ev-n{{font-size:12px;margin-top:3px;line-height:1.5}}
.ev-ty{{display:inline-block;font-size:8px;font-weight:800;text-transform:uppercase;padding:1px 6px;border-radius:10px;margin-right:6px;vertical-align:middle}}
.ev-x{{font-size:11px;color:var(--mut);margin-top:3px;line-height:1.5}}
.note{{font-size:10.5px;color:var(--mut);margin-top:8px;line-height:1.6}}
::-webkit-scrollbar{{height:9px;width:9px}}::-webkit-scrollbar-thumb{{background:#1d3a5c;border-radius:5px}}
</style></head><body>
<div class="hdr">
  <div class="brand">
    <div class="b-op">TAT&nbsp;&nbsp;OPERATING</div>
    <div class="b-wl">WATER<span class="g">LINE</span></div>
    <svg class="swoosh" width="230" height="13" viewBox="0 0 230 13"><defs><linearGradient id="sw" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#6f92b8"/><stop offset="1" stop-color="#c9a24a"/></linearGradient></defs><path d="M2 9 C 70 2, 140 3, 195 6 L 228 1" fill="none" stroke="url(#sw)" stroke-width="2.5" stroke-linecap="round"/></svg>
    <div class="b-tag">Smart Water. <span class="g">Real Results.</span></div>
  </div>
  <div class="hr"><div class="u">Atualizado {d_str}</div><div class="s">Pipeline comercial · fonte Notion · diário</div></div>
</div>
<div class="kpis">
  <div class="kpi"><div class="v">{total}</div><div class="l">Contas</div></div>
  <div class="kpi grn"><div class="v">{em_pipeline}</div><div class="l">Em pipeline</div></div>
  <div class="kpi g"><div class="v">{diag_plus}</div><div class="l">Diagnóstico+</div></div>
  <div class="kpi g"><div class="v">{venc}</div><div class="l">Prazos ≤ 7 dias</div></div>
  <div class="kpi rd"><div class="v">{venc0}</div><div class="l">Prazos vencidos</div></div>
  <div class="kpi"><div class="v">{fleet:,}</div><div class="l">Frota Boeing</div></div>
</div>
<div class="tabs">
  <div class="tabx on" data-p="pipe" onclick="tab('pipe')">🛩️ Pipeline</div>
  <div class="tabx" data-p="cont" onclick="tab('cont')">👥 Contatos <span class="tct">{len(contatos)}</span></div>
  <div class="tabx" data-p="evt" onclick="tab('evt')">📅 Eventos <span class="tct">{len(eventos)}</span></div>
</div>
<div id="p-pipe" class="panel on"><div class="board">{cols}</div></div>
<div id="p-cont" class="panel"><div class="wrap">{contatos_html}</div></div>
<div id="p-evt" class="panel"><div class="wrap">{eventos_html}</div></div>
<div class="ftr">Gerado automaticamente a partir do Notion · atualização diária · <b>TAT Operating · Confidencial — uso interno.</b> Não inclui valores (US$).</div>
<div class="ov" id="ov" onclick="closeD()"></div>
<div class="drw" id="drw"></div>
<script>
const DATA={DATA};
const SC={json.dumps(STAGE_COLOR, ensure_ascii=False)};
const QC={json.dumps(QUAD_COLOR, ensure_ascii=False)};
const TY={json.dumps(TYPE_COLOR, ensure_ascii=False)};
const FLAG={json.dumps(FLAG, ensure_ascii=False)};
const TODAY="{today.isoformat()}";
function fmt(d){{if(!d)return null;const p=d.split('-');return p[2]+'/'+p[1]+'/'+p[0].slice(2);}}
function esc(s){{return String(s==null?'':s).replace(/[&<>]/g,m=>({{'&':'&amp;','<':'&lt;','>':'&gt;'}}[m]));}}
function delta(d){{if(!d)return null;return Math.round((new Date(d)-new Date(TODAY))/864e5);}}
function paint(){{
  DATA.forEach(a=>{{
    const el=document.getElementById('c'+a._i); if(!el)return;
    const qc=QC[a.quad]||'#7c8ba0', flag=FLAG[a.pais]||'🏳️';
    let chips='';
    if(a.quad)chips+='<span class="chip" style="border-color:'+qc+'55;color:'+qc+';background:'+qc+'14">'+esc(a.quad)+'</span>';
    if(a.score!=null)chips+='<span class="chip mut">Score '+a.score+'</span>';
    let meta=[];
    if(a.fleet)meta.push(Math.round(a.fleet)+' Boeing');
    if(a.toques)meta.push(a.toques+' toque(s)');
    if(a.ult)meta.push('últ. '+fmt(a.ult));
    let pz='';
    if(a.prazo){{const dd=delta(a.prazo);
      if(dd<0&&a.estagio!=='Alvo')pz='<span class="pz pz-r">Vencido · '+fmt(a.prazo)+'</span>';
      else if(dd<=7)pz='<span class="pz pz-a">Prazo '+fmt(a.prazo)+' · '+dd+'d</span>';
      else pz='<span class="pz">Prazo '+fmt(a.prazo)+'</span>';}}
    el.innerHTML='<div class="c-top"><div class="c-name">'+esc(a.nome)+'</div><div class="c-flag">'+flag+'</div></div>'
      +'<div class="chips">'+chips+'</div>'+(meta.length?'<div class="c-meta">'+meta.join(' · ')+'</div>':'')+pz;
  }});
}}
function tl(a){{
  const ev=a.eventos||[];
  if(!ev.length)return '<div class="sec">Timeline</div><div class="note">Sem interações registradas.</div>';
  let rows=ev.map(e=>{{
    const c=TY[e.t]||'#7c8ba0';
    return '<div class="ev"><div class="ev-d">'+(e.d?fmt(e.d):'—')+(e.resp?' · '+esc(e.resp):'')+'</div>'
      +'<div class="ev-n"><span class="ev-ty" style="background:'+c+'22;color:'+c+'">'+esc(e.t)+'</span>'
      +'<b>'+esc(e.titulo||'')+'</b>'+(e.desc?'<div class="ev-x">'+esc(e.desc)+'</div>':'')+'</div></div>';
  }}).join('');
  return '<div class="sec">Timeline · '+ev.length+' evento(s)</div><div class="tlw">'+rows+'</div>';
}}
function openD(i){{
  const a=DATA[i]; const sc=SC[a.estagio]||'#7c8ba0', qc=QC[a.quad]||'#7c8ba0', flag=FLAG[a.pais]||'🏳️';
  let pz='—';
  if(a.prazo){{const dd=delta(a.prazo); pz=fmt(a.prazo)+(dd<0?' (vencido)':dd<=7?' ('+dd+'d)':'');}}
  document.getElementById('drw').innerHTML=
   '<div class="drw-h"><button class="drw-x" onclick="closeD()">✕</button>'
   +'<div class="drw-c">'+flag+' '+esc(a.nome)+'</div>'
   +'<div class="drw-s">'+esc(a.pais||'')+(a.fleet?' · '+Math.round(a.fleet)+' Boeing':'')+'</div>'
   +'<div style="margin-top:10px"><span class="chip" style="border-color:'+sc+';color:'+sc+';background:'+sc+'1c">'+a.estagio+'</span>'
   +(a.quad?' <span class="chip" style="border-color:'+qc+'55;color:'+qc+';background:'+qc+'14">'+esc(a.quad)+'</span>':'')+'</div></div>'
   +'<div class="drw-b"><div class="g2">'
   +'<div class="f"><div class="l">Opportunity Score</div><div class="v">'+(a.score!=null?a.score:'—')+'</div></div>'
   +'<div class="f"><div class="l">Propensão</div><div class="v">'+(a.prop!=null?a.prop+' / 10':'—')+'</div></div>'
   +'<div class="f"><div class="l">Prazo</div><div class="v">'+pz+'</div></div>'
   +'<div class="f"><div class="l">Toques</div><div class="v">'+(a.toques||0)+(a.ult?' · últ. '+fmt(a.ult):'')+'</div></div>'
   +(a.sponsor&&a.sponsor!=='—'?'<div class="f wide"><div class="l">Sponsor-alvo</div><div class="v">'+esc(a.sponsor)+'</div></div>':'')
   +(a.caminho?'<div class="f wide"><div class="l">Caminho de acesso</div><div class="v" style="font-weight:600">'+esc(a.caminho)+'</div></div>':'')
   +(a.proxima?'<div class="f wide"><div class="l">Próxima ação</div><div class="v" style="font-weight:600;color:var(--gold2)">'+esc(a.proxima)+'</div></div>':'')
   +'</div>'
   +(a.risco?'<div class="risco"><b>Risco / objeção:</b> '+esc(a.risco)+'</div>':'')
   +tl(a)+'</div>';
  document.getElementById('drw').classList.add('on');document.getElementById('ov').classList.add('on');
}}
function closeD(){{document.getElementById('drw').classList.remove('on');document.getElementById('ov').classList.remove('on');}}
function tab(p){{
  document.querySelectorAll('.panel').forEach(x=>x.classList.remove('on'));
  document.getElementById('p-'+p).classList.add('on');
  document.querySelectorAll('.tabx').forEach(x=>x.classList.toggle('on',x.getAttribute('data-p')===p));
}}
paint();
</script>
</body></html>'''

if __name__ == "__main__":
    main()
