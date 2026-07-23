#!/usr/bin/env python3
"""
TAT WaterLine — Gerador do dashboard PÚBLICO (board Kanban clicável).

Lê Contas + Interações do Notion (API oficial) e gera um index.html com o
funil completo: cards das companhias por estágio, clicáveis para abrir um
detalhe. Mostra NOMES DE CONTA e ESTÁGIOS; NÃO expõe contatos (pessoas),
valores (US$) nem históricos nominais.

Env (GitHub Secrets): NOTION_TOKEN, CONTAS_DS, INTERACOES_DS
"""
import os, sys, json, datetime, urllib.request

NOTION_TOKEN  = os.environ.get("NOTION_TOKEN", "")
CONTAS_DS     = os.environ.get("CONTAS_DS", "77949769-ec49-45d5-95fa-111f6f9d64a1")
INTERACOES_DS = os.environ.get("INTERACOES_DS", "54d6bc50-22b3-4c9a-9eb9-6a492224bbf8")
NOTION_VERSION = "2025-09-03"
API = "https://api.notion.com/v1"

STAGE_ORDER = ["Alvo","Contato","Reunião","Diagnóstico","Comitê","Mandato","Implantação"]
STAGE_COLOR = {"Alvo":"#6b7a90","Contato":"#4f7ee6","Reunião":"#22b8a6","Diagnóstico":"#a06cf0",
               "Comitê":"#f2a900","Mandato":"#12c98a","Implantação":"#10d18a"}
QUAD_COLOR = {"Executar agora":"#12c98a","Converter":"#4f7ee6","Construir acesso":"#a06cf0",
              "Cultivar":"#f2a900","Observar":"#6b7a90"}
FLAG = {"Brasil":"🇧🇷","EAU":"🇦🇪","Panamá":"🇵🇦","EUA":"🇺🇸","Canadá":"🇨🇦","Catar":"🇶🇦",
        "Chile":"🇨🇱","Índia":"🇮🇳","Irlanda":"🇮🇪","Coreia do Sul":"🇰🇷","Turquia":"🇹🇷",
        "Japão":"🇯🇵","Etiópia":"🇪🇹","Angola":"🇦🇴"}

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
    ts = P(pg, n).get("title") or []
    return "".join(t.get("plain_text","") for t in ts)
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

    tmap = {}
    for it in inter:
        d = to_date(dstart(it, "Data"))
        for aid in relids(it, "Conta"):
            e = tmap.setdefault(aid, {"n": 0, "last": None})
            e["n"] += 1
            if d and (e["last"] is None or d > e["last"]):
                e["last"] = d

    accts = []
    for p in contas:
        t = tmap.get(p.get("id"), {"n": 0, "last": None})
        prazo = to_date(dstart(p, "Prazo"))
        accts.append({
            "nome": title(p,"Conta"), "pais": sel(p,"País"),
            "estagio": sel(p,"Estágio") or "Alvo", "quad": sel(p,"Quadrante"),
            "score": num(p,"Opportunity Score"), "fleet": num(p,"Frota Boeing"),
            "prop": num(p,"Propensão"), "prazo": prazo.isoformat() if prazo else None,
            "risco": rtext(p,"Risco / objeção"),
            "toques": t["n"], "ult": t["last"].isoformat() if t["last"] else None,
        })

    total = len(accts)
    em_pipeline = sum(1 for a in accts if a["estagio"] != "Alvo")
    diag_plus = sum(1 for a in accts if a["estagio"] in ("Diagnóstico","Comitê","Mandato","Implantação"))
    fleet = sum(int(a["fleet"] or 0) for a in accts)
    def pdelta(a):
        d = to_date(a["prazo"]);  return (d - today).days if d else None
    venc  = sum(1 for a in accts if pdelta(a) is not None and 0 <= pdelta(a) <= 7)
    venc0 = sum(1 for a in accts if pdelta(a) is not None and pdelta(a) < 0 and a["estagio"] != "Alvo")

    html = render(today, accts, total, em_pipeline, diag_plus, fleet, venc, venc0, len(inter))
    with open("index.html","w",encoding="utf-8") as f:
        f.write(html)
    print(f"OK · {total} contas · {len(inter)} interações · {venc} prazos ≤7d · {venc0} vencidos")

def render(today, accts, total, em_pipeline, diag_plus, fleet, venc, venc0, n_inter):
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
    return f'''<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>TAT WaterLine · Pipeline</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
:root{{--bg:#060f1c;--s1:#0b1a2c;--s2:#102439;--b:#1c3a5c;--b2:#122a44;--blue:#4f7ee6;--amb:#f2a900;--rd:#e8556b;--grn:#12c98a;--tx:#d3e4f5;--mut:#7f97b3;--fn:'Inter',system-ui,-apple-system,sans-serif}}
body{{background:var(--bg);color:var(--tx);font-family:var(--fn);font-size:13px;line-height:1.5;padding-bottom:40px}}
.hdr{{background:linear-gradient(120deg,#081426,#0e2a4e);border-bottom:1px solid var(--b);padding:20px 26px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px}}
.ht{{font-size:18px;font-weight:800}}.hs{{font-size:11px;color:var(--mut);text-transform:uppercase;letter-spacing:.5px;margin-top:3px}}
.upd{{font-size:11px;color:var(--grn);font-weight:700;text-align:right}}
.kpis{{display:flex;gap:10px;padding:16px 26px;flex-wrap:wrap;border-bottom:1px solid var(--b)}}
.kpi{{background:var(--s2);border:1px solid var(--b);border-radius:10px;padding:10px 15px;min-width:104px}}
.kpi .v{{font-size:22px;font-weight:900;letter-spacing:-.5px;line-height:1}}
.kpi.amb .v{{color:var(--amb)}}.kpi.rd .v{{color:var(--rd)}}.kpi.grn .v{{color:var(--grn)}}
.kpi .l{{font-size:9.5px;color:var(--mut);text-transform:uppercase;letter-spacing:.4px;margin-top:5px}}
.board{{display:flex;gap:12px;padding:18px 26px;overflow-x:auto;align-items:flex-start}}
.col{{flex:0 0 232px;background:var(--s1);border:1px solid var(--b);border-radius:11px;padding:10px}}
.col-h{{display:flex;align-items:center;gap:7px;font-size:11px;font-weight:800;text-transform:uppercase;letter-spacing:.4px;margin-bottom:10px}}
.dot{{width:9px;height:9px;border-radius:50%}}.col-n{{margin-left:auto;background:var(--s2);border:1px solid var(--b);border-radius:20px;padding:1px 8px;font-size:10px;color:var(--mut)}}
.card{{background:var(--s2);border:1px solid var(--b);border-left:3px solid var(--mut);border-radius:9px;padding:11px;margin-bottom:9px;cursor:pointer;transition:.15s}}
.card:hover{{border-color:var(--blue);transform:translateY(-1px)}}
.c-top{{display:flex;justify-content:space-between;align-items:flex-start;gap:6px}}
.c-name{{font-size:13px;font-weight:800;line-height:1.2}}.c-flag{{font-size:13px}}
.chips{{display:flex;gap:5px;flex-wrap:wrap;margin:7px 0 5px}}
.chip{{font-size:8.5px;font-weight:700;padding:2px 7px;border-radius:20px;border:1px solid;letter-spacing:.3px;white-space:nowrap}}
.chip.mut{{border-color:var(--b);color:var(--mut)}}
.c-meta{{font-size:10px;color:var(--mut)}}
.pz{{display:inline-block;font-size:9.5px;font-weight:700;color:var(--mut);border:1px solid var(--b);border-radius:5px;padding:2px 7px;margin-top:6px}}
.pz-a{{color:#1a1200;background:var(--amb);border-color:var(--amb)}}
.pz-r{{color:#fff;background:var(--rd);border-color:var(--rd)}}
.empty{{font-size:10px;color:var(--mut);text-align:center;padding:14px 0}}
.ftr{{text-align:center;color:var(--mut);font-size:10.5px;margin-top:10px;padding:0 26px;line-height:1.7}}
.ov{{position:fixed;inset:0;background:rgba(2,8,16,.6);opacity:0;pointer-events:none;transition:.2s;z-index:90}}
.ov.on{{opacity:1;pointer-events:auto}}
.drw{{position:fixed;top:0;right:0;bottom:0;width:min(440px,94vw);background:var(--s1);border-left:1px solid var(--b);transform:translateX(100%);transition:.25s;z-index:100;overflow-y:auto;box-shadow:-12px 0 40px rgba(0,0,0,.5)}}
.drw.on{{transform:translateX(0)}}
.drw-h{{padding:18px 22px;border-bottom:1px solid var(--b);background:linear-gradient(120deg,#0a1c33,#0e2748);position:sticky;top:0}}
.drw-x{{position:absolute;top:15px;right:16px;background:var(--s2);border:1px solid var(--b);color:var(--mut);width:30px;height:30px;border-radius:7px;cursor:pointer;font-size:15px}}
.drw-c{{font-size:20px;font-weight:800}}.drw-s{{font-size:11px;color:var(--mut);margin-top:3px}}
.drw-b{{padding:16px 22px}}
.g2{{display:grid;grid-template-columns:1fr 1fr;gap:9px;margin-bottom:14px}}
.f{{background:var(--s2);border:1px solid var(--b);border-radius:8px;padding:9px 11px}}
.f .l{{font-size:9px;color:var(--mut);text-transform:uppercase;letter-spacing:.4px}}.f .v{{font-size:13px;font-weight:700;margin-top:3px}}
.risco{{font-size:11px;color:#e6b088;background:rgba(230,176,136,.08);border:1px solid rgba(230,176,136,.25);border-radius:8px;padding:9px 11px;line-height:1.5}}
.note{{font-size:10.5px;color:var(--mut);margin-top:14px;line-height:1.6}}
::-webkit-scrollbar{{height:9px;width:9px}}::-webkit-scrollbar-thumb{{background:#1e3d5f;border-radius:5px}}
</style></head><body>
<div class="hdr">
  <div><div class="ht">🛩️ TAT WaterLine · Pipeline</div><div class="hs">Funil comercial · clique num card · sem contatos e sem valores</div></div>
  <div class="upd">Atualizado {d_str}<div class="hs">fonte: Notion · diário</div></div>
</div>
<div class="kpis">
  <div class="kpi"><div class="v">{total}</div><div class="l">Contas</div></div>
  <div class="kpi grn"><div class="v">{em_pipeline}</div><div class="l">Em pipeline</div></div>
  <div class="kpi"><div class="v">{diag_plus}</div><div class="l">Diagnóstico+</div></div>
  <div class="kpi amb"><div class="v">{venc}</div><div class="l">Prazos ≤ 7 dias</div></div>
  <div class="kpi rd"><div class="v">{venc0}</div><div class="l">Prazos vencidos</div></div>
  <div class="kpi"><div class="v">{fleet:,}</div><div class="l">Frota Boeing</div></div>
</div>
<div class="board">{cols}</div>
<div class="ftr">Gerado automaticamente a partir do Notion · atualização diária · TAT Operating · Confidencial. Mostra contas e estágios; não inclui contatos, valores nem históricos nominais.</div>
<div class="ov" id="ov" onclick="closeD()"></div>
<div class="drw" id="drw"></div>
<script>
const DATA={DATA};
const SC={json.dumps(STAGE_COLOR, ensure_ascii=False)};
const QC={json.dumps(QUAD_COLOR, ensure_ascii=False)};
const FLAG={json.dumps(FLAG, ensure_ascii=False)};
const TODAY="{today.isoformat()}";
function fmt(d){{if(!d)return null;const p=d.split('-');return p[2]+'/'+p[1];}}
function esc(s){{return String(s==null?'':s).replace(/[&<>]/g,m=>({{'&':'&amp;','<':'&lt;','>':'&gt;'}}[m]));}}
function delta(d){{if(!d)return null;return Math.round((new Date(d)-new Date(TODAY))/864e5);}}
function paint(){{
  DATA.forEach(a=>{{
    const el=document.getElementById('c'+a._i); if(!el)return;
    const qc=QC[a.quad]||'#6b7a90', flag=FLAG[a.pais]||'🏳️';
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
function openD(i){{
  const a=DATA[i]; const sc=SC[a.estagio]||'#6b7a90', qc=QC[a.quad]||'#6b7a90', flag=FLAG[a.pais]||'🏳️';
  let pz='—';
  if(a.prazo){{const dd=delta(a.prazo);
    pz=fmt(a.prazo)+(dd<0?' (vencido)':dd<=7?' ('+dd+'d)':'');}}
  document.getElementById('drw').innerHTML=
   '<div class="drw-h"><button class="drw-x" onclick="closeD()">✕</button>'
   +'<div class="drw-c">'+flag+' '+esc(a.nome)+'</div>'
   +'<div class="drw-s">'+esc(a.pais||'')+(a.fleet?' · '+Math.round(a.fleet)+' Boeing':'')+'</div>'
   +'<div style="margin-top:9px"><span class="chip" style="border-color:'+sc+';color:'+sc+';background:'+sc+'18">'+a.estagio+'</span>'
   +(a.quad?' <span class="chip" style="border-color:'+qc+'55;color:'+qc+';background:'+qc+'14">'+esc(a.quad)+'</span>':'')+'</div></div>'
   +'<div class="drw-b"><div class="g2">'
   +'<div class="f"><div class="l">Opportunity Score</div><div class="v">'+(a.score!=null?a.score:'—')+'</div></div>'
   +'<div class="f"><div class="l">Propensão</div><div class="v">'+(a.prop!=null?a.prop+' / 10':'—')+'</div></div>'
   +'<div class="f"><div class="l">Prazo</div><div class="v">'+pz+'</div></div>'
   +'<div class="f"><div class="l">Toques</div><div class="v">'+(a.toques||0)+(a.ult?' · últ. '+fmt(a.ult):'')+'</div></div>'
   +'</div>'
   +(a.risco?'<div class="risco"><b>Risco / objeção:</b> '+esc(a.risco)+'</div>':'')
   +'<div class="note">Contatos, valores e histórico nominal ficam no Notion (acesso restrito).</div></div>';
  document.getElementById('drw').classList.add('on');document.getElementById('ov').classList.add('on');
}}
function closeD(){{document.getElementById('drw').classList.remove('on');document.getElementById('ov').classList.remove('on');}}
paint();
</script>
</body></html>'''

if __name__ == "__main__":
    main()
