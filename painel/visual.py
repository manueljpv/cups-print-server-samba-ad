"""Visual do painel: folha de estilo unica (tokens, tema claro e escuro)."""
from flask import make_response

CSS = """
:root{
 --bg:#eef1f5; --surface:#ffffff; --surface-2:#f4f6f9; --line:#dbe1e9;
 --fg:#15202b; --muted:#536274; --faint:#8794a4;
 --brand:#1f3a5f; --brand-fg:#ffffff; --brand-soft:#c9dcf3; --btn:#1f3a5f; --btn-fg:#ffffff;
 --focus:#2b78c2;
 --cor-bg:#efe3fb; --cor-fg:#4a1d7a; --info-bg:#e3edf9; --info-fg:#1f3a5f;
 --ok-bg:#e2f5e8; --ok-fg:#0e5a2b; --ok:#1f9d55;
 --warn-bg:#fff1c9; --warn-fg:#634600; --warn:#d49a00;
 --alert-bg:#ffe3c7; --alert-fg:#733500; --alert:#e5700a;
 --crit-bg:#fde4e4; --crit-fg:#82171a; --crit:#d23b3b;
 --shadow:0 1px 2px rgba(15,30,45,.06),0 6px 18px rgba(15,30,45,.06);
 --r:14px;
 --sans:system-ui,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;
 --mono:ui-monospace,"Cascadia Mono",Consolas,Menlo,monospace;
}
@media (prefers-color-scheme:dark){
 :root{
  --bg:#0e151d; --surface:#16202b; --surface-2:#1b2735; --line:#273546;
  --fg:#e5ecf4; --muted:#93a2b4; --faint:#667587;
  --brand:#0f2740; --brand-fg:#ffffff; --brand-soft:#9fbfe3; --btn:#3b8bd4; --btn-fg:#06121e;
  --focus:#6db0f0;
  --cor-bg:#2f1f45; --cor-fg:#d9b8ff; --info-bg:#1d2d44; --info-fg:#a9c7ee;
  --ok-bg:#12301f; --ok-fg:#86dea6; --ok:#3fbf72;
  --warn-bg:#3a2f0b; --warn-fg:#f2d27c; --warn:#e0b030;
  --alert-bg:#3c2410; --alert-fg:#ffc48a; --alert:#f08a30;
  --crit-bg:#3d1819; --crit-fg:#ffaaaa; --crit:#ee5f5f;
  --shadow:0 1px 2px rgba(0,0,0,.4),0 6px 18px rgba(0,0,0,.3);
  color-scheme:dark;
 }
}
*{box-sizing:border-box}
html{background:var(--bg)}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 var(--sans);
 -webkit-font-smoothing:antialiased}
h1,h2,h3{margin:0;line-height:1.25;text-wrap:balance}
.num{font-variant-numeric:tabular-nums}

/* barra superior */
.topo{background:var(--brand);color:var(--brand-fg)}
.topo .in{max-width:980px;margin:0 auto;padding:0 16px;display:flex;align-items:stretch;gap:6px;
 flex-wrap:wrap}
.marca{display:flex;align-items:center;gap:10px;font-weight:650;letter-spacing:.01em;
 padding:12px 18px 12px 0;margin-right:6px}
.marca svg{width:22px;height:22px;opacity:.9}
.topo nav{display:flex;align-items:stretch;gap:2px}
.topo nav a{color:var(--brand-soft);text-decoration:none;padding:14px 14px 11px;
 border-bottom:3px solid transparent;font-weight:500}
.topo nav a:hover{color:#fff}
.topo nav a.at{color:#fff;border-bottom-color:#fff}
.topo .esp{flex:1}
.usuario{display:flex;align-items:center;gap:10px;padding:8px 0;font-size:14px}
.usuario .quem{color:var(--brand-soft)}
.usuario form{margin:0}
.btn-sair{background:transparent;color:var(--brand-fg);border:1px solid rgba(255,255,255,.35);
 padding:5px 12px;border-radius:8px;font:inherit;font-size:13px;cursor:pointer}
.btn-sair:hover{background:rgba(255,255,255,.12)}

/* pagina */
.pagina{max-width:980px;margin:0 auto;padding:26px 16px 48px;display:grid;gap:14px}
.cab h1{font-size:24px;font-weight:700;letter-spacing:-.01em}
.cab p{margin:4px 0 0;color:var(--muted);font-size:14px;max-width:62ch}
.card{background:var(--surface);border:1px solid var(--line);border-radius:var(--r);
 box-shadow:var(--shadow)}
.vazio{padding:28px}
.vazio p{color:var(--muted)}

/* faixas: aviso de prazo e mensagens */
.faixa{display:flex;gap:12px;align-items:flex-start;padding:14px 16px;border-radius:var(--r);
 border:1px solid transparent}
.faixa .ic{flex:none;width:30px;height:30px;border-radius:50%;display:grid;place-items:center;color:#fff}
.faixa .ic svg{width:18px;height:18px}
.faixa b{display:block;font-size:15px}
.faixa span{font-size:14px}
.faixa.amarelo{background:var(--warn-bg);color:var(--warn-fg);border-color:color-mix(in srgb,var(--warn) 35%,transparent)}
.faixa.amarelo .ic{background:var(--warn)}
.faixa.laranja{background:var(--alert-bg);color:var(--alert-fg);border-color:color-mix(in srgb,var(--alert) 40%,transparent)}
.faixa.laranja .ic{background:var(--alert)}
.faixa.vermelho,.faixa.erro{background:var(--crit-bg);color:var(--crit-fg);border-color:color-mix(in srgb,var(--crit) 40%,transparent)}
.faixa.vermelho .ic,.faixa.erro .ic{background:var(--crit)}
.faixa.ok{background:var(--ok-bg);color:var(--ok-fg);border-color:color-mix(in srgb,var(--ok) 35%,transparent)}
.faixa.ok .ic{background:var(--ok)}

/* estado principal */
.estado{display:grid;grid-template-columns:auto 1fr;gap:16px;align-items:center;padding:20px 22px;
 border-radius:var(--r);border:1px solid transparent}
.estado .sel{width:48px;height:48px;border-radius:50%;display:grid;place-items:center;color:#fff}
.estado .sel svg{width:26px;height:26px}
.estado h2{font-size:22px;font-weight:700;letter-spacing:-.01em}
.estado p{margin:2px 0 0;font-size:14px;opacity:.88}
.estado.ok{background:var(--ok-bg);color:var(--ok-fg);border-color:color-mix(in srgb,var(--ok) 35%,transparent)}
.estado.ok .sel{background:var(--ok)}
.estado.atencao{background:var(--warn-bg);color:var(--warn-fg);border-color:color-mix(in srgb,var(--warn) 35%,transparent)}
.estado.atencao .sel{background:var(--warn)}
.estado.falha{background:var(--crit-bg);color:var(--crit-fg);border-color:color-mix(in srgb,var(--crit) 40%,transparent)}
.estado.falha .sel{background:var(--crit)}

/* fatos */
.fatos{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:12px}
.fatos.quatro{grid-template-columns:repeat(4,minmax(0,1fr))}
@media (max-width:900px){.fatos.quatro{grid-template-columns:repeat(2,minmax(0,1fr))}}
.fato{padding:16px 18px}
.fato .rot{font-size:12px;text-transform:uppercase;letter-spacing:.07em;color:var(--muted);font-weight:600}
.fato .val{font-size:21px;font-weight:650;margin-top:4px;font-variant-numeric:tabular-nums;letter-spacing:-.01em}
.fato .sub{font-size:13px;color:var(--muted);margin-top:2px}
.pilula{display:inline-flex;align-items:center;gap:6px;padding:2px 10px;border-radius:999px;
 font-size:13px;font-weight:600}
.pilula.ok{background:var(--ok-bg);color:var(--ok-fg)}
.pilula.falha{background:var(--crit-bg);color:var(--crit-fg)}
.pilula.nd{background:var(--surface-2);color:var(--muted)}

/* ciclo da senha */
.ciclo{padding:16px 18px}
.ciclo .topo-c{display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;align-items:baseline}
.ciclo .rot{font-size:12px;text-transform:uppercase;letter-spacing:.07em;color:var(--muted);font-weight:600}
.ciclo .dia{font-size:14px;color:var(--muted)}
.trilho{position:relative;height:10px;border-radius:999px;background:var(--surface-2);
 border:1px solid var(--line);margin:12px 0 8px;overflow:visible}
.trilho .cheio{position:absolute;left:0;top:-1px;bottom:-1px;border-radius:999px;background:var(--ok);
 min-width:10px}
.trilho .cheio.amarelo{background:var(--warn)}
.trilho .cheio.laranja{background:var(--alert)}
.trilho .cheio.vermelho{background:var(--crit)}
.trilho .hoje{position:absolute;top:50%;width:16px;height:16px;border-radius:50%;background:var(--surface);
 border:3px solid var(--ok);transform:translate(-50%,-50%)}
.trilho .cheio.amarelo~.hoje{border-color:var(--warn)}
.trilho .cheio.laranja~.hoje{border-color:var(--alert)}
.trilho .cheio.vermelho~.hoje{border-color:var(--crit)}
.pontas{display:flex;justify-content:space-between;gap:12px;font-size:13px;color:var(--muted);
 font-variant-numeric:tabular-nums}

/* testes */
.testes{padding:6px 0}
.testes .cab-t{display:flex;justify-content:space-between;align-items:center;padding:12px 18px 8px}
.testes h3{font-size:15px}
.teste{display:grid;grid-template-columns:26px 1fr auto;gap:12px;align-items:center;padding:9px 18px;
 border-top:1px solid var(--line)}
.teste .bolha{width:22px;height:22px;border-radius:50%;display:grid;place-items:center;color:#fff;background:var(--ok)}
.teste .bolha.nao{background:var(--crit)}
.teste .bolha svg{width:13px;height:13px}
.teste .det{font-family:var(--mono);font-size:12.5px;color:var(--muted);text-align:right}

/* acao */
.acao{overflow:hidden}
.acao summary{list-style:none;cursor:pointer;display:flex;align-items:center;gap:14px;padding:16px 18px}
.acao summary::-webkit-details-marker{display:none}
.acao summary .t{flex:1;min-width:0}
.acao summary b{display:block;font-size:15px}
.acao summary span{font-size:13px;color:var(--muted)}
.acao summary .seta{width:20px;height:20px;color:var(--muted);transition:transform .15s}
.acao summary .seta svg{width:100%;height:100%}
.acao[open] summary .seta{transform:rotate(180deg)}
.acao[open] summary{border-bottom:1px solid var(--line)}
.acao .corpo{padding:16px 18px 18px;display:grid;gap:12px}
.acao .nota{font-size:13px;color:var(--muted);margin:0}
.linha-form{display:grid;grid-template-columns:minmax(0,1.6fr) minmax(0,1fr) auto;gap:12px;align-items:end}
.campo label{display:block;font-size:12.5px;font-weight:600;color:var(--muted);margin-bottom:5px}
.campo input,.caixa-login input{width:100%;height:42px;padding:0 12px;border-radius:9px;
 border:1px solid var(--line);background:var(--surface);color:var(--fg);font:inherit}
.campo input:focus,.caixa-login input:focus,.btn:focus-visible,.acao summary:focus-visible,
.btn-sair:focus-visible,.topo nav a:focus-visible{outline:3px solid var(--focus);outline-offset:1px}
.btn{height:42px;padding:0 20px;border-radius:9px;border:0;background:var(--btn);color:var(--btn-fg);
 font:inherit;font-weight:650;cursor:pointer}
.btn:hover{filter:brightness(1.08)}
.andamento{display:grid;gap:10px;padding:18px}
.andamento b{font-size:15px}
.barra{height:6px;border-radius:999px;background:var(--surface-2);overflow:hidden;border:1px solid var(--line)}
.barra i{display:block;height:100%;width:35%;background:var(--btn);border-radius:999px;
 animation:corre 1.2s ease-in-out infinite}
@keyframes corre{0%{margin-left:-35%}100%{margin-left:100%}}
@media (prefers-reduced-motion:reduce){.barra i{animation:none;width:100%;opacity:.6}}

/* login */
.login-wrap{min-height:100vh;display:grid;place-items:center;padding:24px 16px}
.caixa-login{width:min(400px,100%);padding:28px 26px;display:grid;gap:14px}
.caixa-login .logo{display:flex;align-items:center;gap:12px}
.caixa-login .logo .sel{width:40px;height:40px;border-radius:11px;background:var(--brand);color:#fff;
 display:grid;place-items:center}
.caixa-login .logo svg{width:22px;height:22px}
.caixa-login h1{font-size:20px}
.caixa-login p.sub{margin:0;color:var(--muted);font-size:13.5px}
.caixa-login label{display:block;font-size:12.5px;font-weight:600;color:var(--muted);margin-bottom:5px}
.caixa-login .btn{width:100%}
.caixa-login .rodape{font-size:12.5px;color:var(--muted);border-top:1px solid var(--line);padding-top:12px}

/* permissoes */
.cab-t{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:12px 18px 8px}
.cab-t h3{font-size:15px}
.pilula.cor{background:var(--cor-bg);color:var(--cor-fg)}
.pilula.info{background:var(--info-bg);color:var(--info-fg)}
.pilula.atencao{background:var(--warn-bg);color:var(--warn-fg)}
.abas{display:flex;gap:4px;flex-wrap:wrap;align-items:flex-end;border-bottom:1px solid var(--line);margin-top:4px}
.abas a{padding:10px 14px;text-decoration:none;color:var(--muted);font-weight:600;
 border-bottom:3px solid transparent;margin-bottom:-1px;border-radius:8px 8px 0 0}
.abas a:hover{color:var(--fg)}
.abas a.at{color:var(--fg);border-bottom-color:var(--btn)}
.abas .esp{flex:1}
.seletor{display:flex;flex-wrap:wrap;gap:8px;margin:2px 0 2px}
.seletor a{display:flex;flex-direction:column;gap:1px;padding:8px 14px;border:1px solid var(--line);border-radius:12px;
 background:var(--surface);color:var(--fg);text-decoration:none;font-weight:600;font-size:14px;min-width:0}
.seletor a small{font-weight:500;font-size:12px;color:var(--muted)}
.seletor a:hover{border-color:var(--faint)}
.seletor a.at{border-color:var(--btn);box-shadow:inset 0 0 0 1px var(--btn)}
.acessos{display:flex;flex-wrap:wrap;gap:6px}
.abas a.atualizar{font-weight:500;font-size:13px;padding:10px 4px}
.tabela-wrap{overflow-x:auto}
table.t.fixa{table-layout:fixed}
.t.fixa td{overflow-wrap:anywhere}
.ord-b{background:none;border:0;padding:0;margin:0;font:inherit;color:inherit;text-transform:inherit;
 letter-spacing:inherit;cursor:pointer;display:inline-flex;align-items:center;gap:6px}
.ord-b:hover{color:var(--fg)}
.ord-b:focus-visible{outline:3px solid var(--focus);outline-offset:2px;border-radius:4px}
.t th[aria-sort=ascending] .ord-b{color:var(--fg)}
.t th[aria-sort=ascending] .ord-b::after{content:"▲";font-size:9px}
table.t{width:100%;border-collapse:collapse;font-size:14px}
.t th{text-align:left;font-size:12px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);
 font-weight:600;padding:8px 18px}
.t td{padding:9px 18px;border-top:1px solid var(--line);vertical-align:middle}
.t .mono{font-family:var(--mono);font-size:13px}
.sub-t{color:var(--muted);font-size:13px}
.tag{font-size:12px;color:var(--crit-fg);background:var(--crit-bg);padding:1px 8px;border-radius:999px}
.cab-t.fila{align-items:flex-start;border-bottom:1px solid var(--line);padding-bottom:12px}
.cab-t.fila h3{font-size:17px}
.grade2{display:grid;grid-template-columns:1fr;gap:0}
.grade2>div+div{border-top:1px solid var(--line)}
.sub-cab{display:flex;justify-content:space-between;align-items:center;padding:12px 18px 6px}
.rodape-card{margin:0;padding:12px 18px;font-size:13px;color:var(--muted);border-top:1px solid var(--line)}
.rodape-card.nota-topo{border-top:0;padding-top:0}
.busca{display:flex;gap:10px;padding:16px 18px}
.busca input{flex:1;min-width:0;height:42px;padding:0 12px;border-radius:9px;border:1px solid var(--line);
 background:var(--surface);color:var(--fg);font:inherit}
.busca input:focus{outline:3px solid var(--focus);outline-offset:1px}
.acao.depto summary .chips{display:flex;gap:6px;flex-wrap:wrap;justify-content:flex-end}

/* etapa 2a: lista de alteracoes */
.t th.chk,.t td.chk{padding:9px 0 9px 14px;text-align:center}
.t th.chk{padding-top:8px;padding-bottom:8px}
.chk input{width:18px;height:18px;accent-color:var(--btn);cursor:pointer}
.so-leitor{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}
.barra-acao{display:flex;flex-wrap:wrap;gap:12px;align-items:end;padding:14px 18px}
.barra-acao .campo{flex:1 1 280px;min-width:0}
.barra-acao .nota{flex:1 1 100%;margin:0;font-size:13px;color:var(--muted)}
.campo select{width:100%;height:42px;padding:0 10px;border-radius:9px;border:1px solid var(--line);
 background:var(--surface);color:var(--fg);font:inherit}
.campo select:focus{outline:3px solid var(--focus);outline-offset:1px}
.lista-alt,.lote{overflow:hidden}
.lista-alt form.aplicar{padding:14px 18px;border-top:1px solid var(--line);margin:0}
.linha-form.dois{grid-template-columns:minmax(0,1fr) auto}
.lista-alt form.esvazia,.lote form.fecha{padding:0 18px 14px;margin:0}
.btn-sec{height:36px;padding:0 14px;border-radius:9px;border:1px solid var(--line);background:transparent;
 color:var(--fg);font:inherit;font-weight:600;cursor:pointer}
.btn-sec:hover{border-color:var(--faint)}
.btn-sec:focus-visible,.mini:focus-visible{outline:3px solid var(--focus);outline-offset:1px}
.mini{height:30px;padding:0 10px;border-radius:8px;border:1px solid var(--line);background:transparent;
 color:var(--fg);font:inherit;font-size:13px;cursor:pointer}
.mini:hover{border-color:var(--crit);color:var(--crit-fg)}
.t td.acoes-l{text-align:right;white-space:nowrap}
.t td.acoes-l form{margin:0}
.passo{margin-top:2px}
/* etapa 2c: sugestoes do GLPI dentro da lista */
.sug{border-top:1px solid var(--line)}
.pc-op{display:flex;align-items:center;gap:8px;flex-wrap:wrap;padding:3px 0;cursor:pointer}
.pc-op input{width:18px;height:18px;accent-color:var(--btn);cursor:pointer}
.pc-op input:disabled{cursor:default}
/* etapa 2b: computadores */
.rodape-acao{padding:12px 18px;border-top:1px solid var(--line)}
.rodape-acao .sub-t{margin-left:12px}

@media (max-width:640px){
 .linha-form{grid-template-columns:1fr}
 .estado{grid-template-columns:1fr}
 .topo .in{gap:0}
 .usuario{width:100%;justify-content:space-between}
}
"""


def registrar(app):
    @app.get("/estilo.css")
    def estilo_css():
        r = make_response(CSS)
        r.headers["Content-Type"] = "text/css; charset=utf-8"
        return r
