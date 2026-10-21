"""Pagina 2 do painel: permissoes de impressao (etapa 1: somente leitura)."""
import unicodedata
from datetime import datetime

from flask import g, make_response, request

import ad_leitura as AD
import auth
import impressoras as REG

VISOES = [("usuario", "Busca por usuário"), ("departamento", "Por departamento"),
          ("impressora", "Por impressora"), ("computadores", "Computadores sem grupo")]
OCULTAR_DEPTOS_PCS = {"servidores"}     # servidores nao precisam de impressora
MIN_BUSCA = 2


def agora():
    return datetime.now()


def _k(s):
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().casefold()


CORPO = """
{% macro ico(n) -%}
{%- if n == 'seta' -%}<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M6 9l6 6 6-6"/></svg>
{%- elif n == 'ok' -%}<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg>
{%- elif n == 'aviso' -%}<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 4l9.5 16.5h-19z"/><path d="M12 10.5v4M12 17.6v.01"/></svg>
{%- endif -%}
{%- endmacro %}
{% macro acessos(u) -%}
<div class="acessos">{% set tem = namespace(v=false) %}
{% for i in imps %}{% set n = u.acesso[i.id] %}{% if n %}{% set tem.v = true %}<span class="pilula {{ niv[i.id][n].pilula }}">{{ i.nome }}{% if i.niveis|length > 1 %} · {{ niv[i.id][n].rotulo }}{% endif %}</span>{% endif %}{% endfor %}
{% if not tem.v %}<span class="pilula nd">sem acesso</span>{% endif %}</div>
{%- endmacro %}
{% macro cab(k, rot) -%}<th aria-sort="{{ 'ascending' if k == 'nome' else 'none' }}"><button type="button" class="ord-b" data-k="{{ k }}" title="Ordenar por {{ rot|lower }}">{{ rot }}</button></th>{%- endmacro %}
{% macro tabela_gente(lista, mostrar_depto, mostrar_acesso=true) -%}
<div class="tabela-wrap"><table class="t fixa ord"><colgroup>{% if mostrar_depto and mostrar_acesso %}<col style="width:26%"><col style="width:18%"><col style="width:30%"><col style="width:26%">{% elif mostrar_depto %}<col style="width:34%"><col style="width:22%"><col style="width:44%">{% else %}<col style="width:38%"><col style="width:24%"><col style="width:38%">{% endif %}</colgroup>
<thead><tr>{{ cab('nome', 'Nome') }}{{ cab('login', 'Login') }}{% if mostrar_depto %}{{ cab('depto', 'Departamento') }}{% endif %}{% if mostrar_acesso %}<th>Acesso</th>{% endif %}</tr></thead><tbody>
{% for u in lista %}<tr><td data-v="{{ u.nome }}">{{ u.nome }}{% if not u.ativo %} <span class="tag">conta desativada</span>{% endif %}</td>
<td class="mono" data-v="{{ u.login }}">{{ u.login }}</td>
{% if mostrar_depto %}<td data-v="{{ u.depto }}">{{ u.depto }}{% if u.sub %} <span class="sub-t">› {{ u.sub }}</span>{% endif %}</td>{% endif %}
{% if mostrar_acesso %}<td>{{ acessos(u) }}</td>{% endif %}</tr>
{% endfor %}</tbody></table></div>
{%- endmacro %}
{% macro seletor(v, contagens, unidade) -%}
<div class="seletor" role="navigation" aria-label="Impressoras">
{% for i in imps %}<a href="/permissoes?v={{ v }}&amp;p={{ i.id }}" class="{{ 'at' if i.id == p }}">{{ i.nome }}<small>{{ contagens[i.id] }} {{ unidade }}</small></a>{% endfor %}</div>
{%- endmacro %}

<div class="pagina">
<div class="cab"><h1>{{ titulo }}</h1>
<p>Quem pode imprimir, por impressora, departamento e usuário. Somente leitura: nada aqui altera o AD.</p></div>

{% if erro %}<div class="faixa erro"><div class="ic">{{ ico('aviso') }}</div>
<div><b>Não foi possível ler o AD</b><span>{{ erro }}</span></div></div>
{% else %}

{% if r.atencao %}<section class="estado atencao"><div class="sel">{{ ico('aviso') }}</div>
<div><h2>{{ r.atencao|length }} {{ 'ponto de atenção' if r.atencao|length == 1 else 'pontos de atenção' }}</h2>
<p>{{ r.atencao|join(' · ') }}</p></div></section>
{% else %}<section class="estado ok"><div class="sel">{{ ico('ok') }}</div>
<div><h2>Permissões em ordem</h2>
<p>{{ r.com_acesso }} pessoas com acesso a pelo menos uma das {{ imps|length }} {{ 'impressora' if imps|length == 1 else 'impressoras' }} e {{ r.pcs_filtro }} computadores no filtro. Nenhuma conta desativada ou fora das OUs. Lido às {{ r.hora }}.</p></div></section>{% endif %}

<div class="fatos quatro">
<div class="card fato"><div class="rot">Impressoras</div><div class="val">{{ imps|length }}</div><div class="sub">cadastradas no painel</div></div>
<div class="card fato"><div class="rot">Pessoas com acesso</div><div class="val">{{ r.com_acesso }}</div><div class="sub">em pelo menos uma impressora</div></div>
<div class="card fato"><div class="rot">Computadores no filtro</div><div class="val">{{ r.pcs_filtro }}</div><div class="sub">em pelo menos uma impressora</div></div>
<div class="card fato"><div class="rot">Usuários no AD</div><div class="val">{{ r.n_ativos }}</div><div class="sub">{{ r.n_deptos }} departamentos</div></div>
</div>

<nav class="abas" aria-label="Visões">
{% for k, rot in visoes %}<a href="/permissoes?v={{ k }}{% if k in ('impressora','computadores') %}&amp;p={{ p }}{% endif %}" class="{{ 'at' if k == v }}">{{ rot }}</a>{% endfor %}
<span class="esp"></span><a class="atualizar" href="/permissoes?v={{ v }}&amp;p={{ p }}{% if q %}&amp;q={{ q|urlencode }}{% endif %}&amp;r=1">Atualizar agora</a>
</nav>

{% if v == 'impressora' %}
{{ seletor('impressora', r.cont_acesso, 'com acesso') }}
{% set f = sel %}{% set x = r.por[f.id] %}
<section class="card"><div class="cab-t fila"><div><h3>{{ f.nome }}</h3>
<span class="sub-t">{{ f.modelo }} · {{ f.ip }} · {{ f.local }}</span></div>
<span class="pilula info">{{ x.com_acesso }} {{ 'pessoa' if x.com_acesso == 1 else 'pessoas' }}</span></div>
<div class="grade2">
{% for n in f.niveis %}<div><div class="sub-cab"><b>{{ n.rotulo }}</b><span class="pilula {{ n.pilula }}">{{ x.niveis[n.id]|length }}</span></div>
{% if x.niveis[n.id] %}{{ tabela_gente(x.niveis[n.id], true, false) }}{% else %}<p class="rodape-card">Ninguém neste nível.</p>{% endif %}</div>{% endfor %}
</div>
<p class="rodape-card">{% if f.niveis|length > 1 %}Cada pessoa aparece só no maior nível que tem. {% endif %}Os demais {{ x.sem_acesso }} usuários ativos estão sem acesso a esta impressora.</p>
</section>
<section class="card"><div class="cab-t"><h3>Computadores no filtro da {{ f.nome }}</h3><span class="pilula ok">{{ x.pcs|length }}</span></div>
{% if x.pcs %}<div class="tabela-wrap"><table class="t fixa ord"><colgroup><col style="width:56%"><col style="width:44%"></colgroup><thead><tr>{{ cab('nome', 'Computador') }}{{ cab('depto', 'Departamento') }}</tr></thead><tbody>
{% for pc in x.pcs %}<tr><td class="mono" data-v="{{ pc.nome }}">{{ pc.nome }}{% if not pc.ativo %} <span class="tag">desativado</span>{% endif %}</td><td data-v="{{ pc.depto }}">{{ pc.depto }}{% if pc.nivel_ou %} <span class="sub-t">› {{ pc.nivel_ou }}</span>{% endif %}</td></tr>
{% endfor %}</tbody></table></div>{% else %}<p class="rodape-card">Nenhum computador no grupo {{ f.grupo_pcs }}.</p>{% endif %}</section>

{% elif v == 'departamento' %}
{% for d in r.deptos %}
<details class="card acao depto"><summary><div class="t"><b>{{ d.nome }}</b><span>{{ d.total }} {{ 'pessoa' if d.total == 1 else 'pessoas' }}</span></div>
<div class="chips">{% if d.n_acesso %}<span class="pilula info">{{ d.n_acesso }} com acesso</span>{% else %}<span class="pilula nd">sem acesso</span>{% endif %}</div>
<div class="seta">{{ ico('seta') }}</div></summary>
{{ tabela_gente(d.lista, false) }}</details>
{% endfor %}

{% elif v == 'usuario' %}
<section class="card"><form class="busca" method="get" action="/permissoes">
<input type="hidden" name="v" value="usuario">
<input name="q" value="{{ q }}" placeholder="Nome ou login (mínimo 2 letras)" maxlength="40" autofocus aria-label="Buscar usuário">
<button class="btn" type="submit">Buscar</button></form>
{% if q and q|length < min_busca %}<p class="rodape-card">Digite pelo menos {{ min_busca }} letras.</p>
{% elif q and not r.achados %}<p class="rodape-card">Nenhum usuário encontrado para "{{ q }}".</p>
{% elif r.achados %}{{ tabela_gente(r.achados, true) }}
{% if r.mais %}<p class="rodape-card">Mostrando os {{ r.achados|length }} primeiros. Refine a busca.</p>{% endif %}
{% else %}<p class="rodape-card">Digite um nome ou login para ver o departamento e o acesso às impressoras.</p>{% endif %}</section>

{% elif v == 'computadores' %}
{{ seletor('computadores', r.cont_sem, 'sem o grupo') }}
<section class="card"><div class="cab-t"><h3>Computadores fora do filtro da {{ sel.nome }}</h3>
<span class="pilula {{ 'ok' if not r.n_sem else 'atencao' }}">{{ r.n_sem }} de {{ r.n_pcs_total }}</span></div>
<p class="rodape-card nota-topo">Computadores das OUs de departamento que ainda não estão no grupo {{ sel.grupo_pcs }}, o filtro que libera essa impressora pela GPO. A OU Servidores não entra na conta.</p></section>
{% for d in r.pcs_deptos %}
<details class="card acao depto"><summary><div class="t"><b>{{ d.nome }}</b><span>{{ d.itens|length }} sem o grupo</span></div><div class="seta">{{ ico('seta') }}</div></summary>
<div class="tabela-wrap"><table class="t"><thead><tr><th>Computador</th><th>Nível da OU</th></tr></thead><tbody>
{% for pc in d.itens %}<tr><td class="mono">{{ pc.nome }}</td><td>{{ pc.nivel_ou or '—' }}</td></tr>{% endfor %}</tbody></table></div></details>
{% endfor %}
{% endif %}
{% endif %}
<script src="/ordenar.js" defer></script>
</div>"""


def _imps():
    return REG.IMPRESSORAS


def _tem(u):
    return any(u["acesso"].values())


def _resumo(d, imps):
    ativos = [u for u in d["usuarios"] if u["ativo"] and not u.get("fora")]
    com_acesso = [u for u in d["usuarios"] if u["ativo"] and _tem(u)]
    desativados = sorted((u for u in d["usuarios"] if not u["ativo"] and _tem(u)), key=lambda u: _k(u["nome"]))
    fora = [u for u in d["usuarios"] if u.get("fora")]
    pcs_fora = [x for x in d["pcs"] if x.get("fora")]
    atencao = []
    if desativados:
        atencao.append("Conta desativada ainda em grupo de impressora: " + ", ".join(
            f"{u['nome']} ({u['login']})" for u in desativados))
    if fora or pcs_fora:
        atencao.append("Fora das OUs (conferir no AD): " + ", ".join(
            sorted({u["nome"] for u in fora} | {x["nome"] for x in pcs_fora})))
    if d.get("grupos_ausentes"):
        atencao.append("Grupo do cadastro não encontrado no AD: " + ", ".join(d["grupos_ausentes"]))
    por = {}
    for i in imps:
        niveis = {n["id"]: sorted((u for u in d["usuarios"] if u["ativo"] and u["acesso"][i["id"]] == n["id"]),
                                  key=lambda u: _k(u["nome"])) for n in i["niveis"]}
        tot = sum(len(x) for x in niveis.values())
        pcs = sorted((p for p in d["pcs"] if p["filtro"][i["id"]]), key=lambda p: _k(p["nome"]))
        por[i["id"]] = {"niveis": niveis, "com_acesso": tot, "pcs": pcs,
                        "sem_acesso": sum(1 for u in ativos if not u["acesso"][i["id"]])}
    return {"atencao": atencao, "com_acesso": len(com_acesso),
            "pcs_filtro": sum(1 for p in d["pcs"] if any(p["filtro"].values())),
            "n_ativos": len(ativos), "n_deptos": len({u["depto"] for u in ativos}),
            "por": por, "cont_acesso": {k: x["com_acesso"] for k, x in por.items()},
            "hora": datetime.fromtimestamp(d["quando"]).strftime("%H:%M")}


def _deptos(d):
    por = {}
    for u in d["usuarios"]:
        if u["ativo"] or _tem(u):
            por.setdefault(u["depto"], []).append(u)
    saida = []
    for nome in sorted(por, key=_k):
        lista = sorted(por[nome], key=lambda u: _k(u["nome"]))
        saida.append({"nome": nome, "lista": lista, "total": len(lista),
                      "n_acesso": sum(1 for u in lista if u["ativo"] and _tem(u))})
    return saida


def _busca(d, q):
    t = _k(q)
    achados = [u for u in d["usuarios"] if t in _k(u["nome"]) or t in _k(u["login"])]
    achados.sort(key=lambda u: _k(u["nome"]))
    return achados[:50], len(achados) > 50


def _pcs_candidatos(d):
    return [p for p in d["pcs"] if p["ativo"] and _k(p["depto"]) not in OCULTAR_DEPTOS_PCS
            and not p["depto"].startswith("(fora")]


def _pcs_sem_grupo(d, pid, imps):
    ativos = _pcs_candidatos(d)
    sem = [p for p in ativos if not p["filtro"][pid]]
    por = {}
    for p in sem:
        por.setdefault(p["depto"], []).append(p)
    deptos = [{"nome": n, "itens": sorted(por[n], key=lambda p: _k(p["nome"]))}
              for n in sorted(por, key=_k)]
    cont = {i["id"]: sum(1 for p in ativos if not p["filtro"][i["id"]]) for i in imps}
    return {"n_sem": len(sem), "n_pcs_total": len(ativos), "pcs_deptos": deptos, "cont_sem": cont}


ORDENAR_JS = """(function(){
var col=new Intl.Collator('pt-BR',{sensitivity:'base',numeric:true});
function val(tr,i){var td=tr.cells[i];if(!td)return '';var v=td.getAttribute('data-v');return v===null?td.textContent.trim():v;}
function idx(t,k){var ths=t.querySelectorAll('thead th');for(var i=0;i<ths.length;i++){var b=ths[i].querySelector('.ord-b');if(b&&b.getAttribute('data-k')===k)return i;}return -1;}
function ordenar(k){
 document.querySelectorAll('table.ord').forEach(function(t){
  var i=idx(t,k);if(i<0)return;
  var tb=t.tBodies[0];var rows=Array.prototype.slice.call(tb.rows);
  rows.sort(function(a,b){return col.compare(val(a,i),val(b,i))||col.compare(val(a,0),val(b,0));});
  rows.forEach(function(r){tb.appendChild(r);});
  t.querySelectorAll('thead th').forEach(function(th,j){th.setAttribute('aria-sort',j===i?'ascending':'none');});
 });
}
document.addEventListener('click',function(e){var b=e.target.closest&&e.target.closest('.ord-b');if(b)ordenar(b.getAttribute('data-k'));});
})();
"""


def registrar(app, requer, pagina):
    @app.get("/ordenar.js")
    def ordenar_js():
        r = make_response(ORDENAR_JS)
        r.headers["Content-Type"] = "application/javascript; charset=utf-8"
        return r

    @app.get("/permissoes")
    @requer("ti")
    def p_permissoes():
        imps = _imps()
        v = request.args.get("v", "usuario")
        if v not in dict(VISOES):
            v = "impressora"
        ids = [i["id"] for i in imps]
        p = request.args.get("p", "")
        if p not in ids:
            p = ids[0]
        sel = next(i for i in imps if i["id"] == p)
        q = request.args.get("q", "").strip()[:40]
        dados = {"erro": None, "r": {}}
        try:
            d = AD.carregar(forcar=request.args.get("r") == "1")
        except AD.ErroAD as e:
            auth.auditar("erro_leitura_ad", g.sess["usuario"], request.remote_addr or "-", str(e))
            dados["erro"] = ("O painel não conseguiu consultar o domínio com a conta "
                             "svc-painel-leitura. Avise a TI (verifique a senha e o LDAPS).")
        else:
            r = _resumo(d, imps)
            if v == "departamento":
                r["deptos"] = _deptos(d)
            elif v == "usuario":
                r["achados"], r["mais"] = (_busca(d, q) if len(q) >= MIN_BUSCA else ([], False))
            elif v == "computadores":
                r.update(_pcs_sem_grupo(d, p, imps))
            dados["r"] = r
        niv = {i["id"]: {n["id"]: n for n in i["niveis"]} for i in imps}
        return pagina("Permissões de impressão", CORPO, "per", v=v, q=q, p=p, sel=sel, visoes=VISOES,
                      imps=imps, niv=niv, min_busca=MIN_BUSCA, **dados)
