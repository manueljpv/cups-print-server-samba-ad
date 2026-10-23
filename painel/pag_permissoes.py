"""Pagina 2 do painel: permissoes de impressao (etapa 1 leitura; 2a pessoas; 2b computadores no _PCs)."""
import unicodedata
from datetime import datetime

from urllib.parse import urlencode, urlsplit

from flask import g, make_response, redirect, request

import ad_leitura as AD
import auth
import escrita_grupos as ESC
import glpi as GLPI
import impressoras as REG

VISOES = [("usuario", "Busca por usuário"), ("departamento", "Por departamento"),
          ("impressora", "Por impressora"), ("computadores", "Computadores")]
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
{% macro ocultos() -%}<input type="hidden" name="v" value="{{ v }}"><input type="hidden" name="q" value="{{ q }}"><input type="hidden" name="p" value="{{ p }}">{%- endmacro %}
{% macro cab(k, rot) -%}<th aria-sort="{{ 'ascending' if k == 'nome' else 'none' }}"><button type="button" class="ord-b" data-k="{{ k }}" title="Ordenar por {{ rot|lower }}">{{ rot }}</button></th>{%- endmacro %}
{% macro tabela_gente(lista, mostrar_depto, mostrar_acesso=true) -%}
<div class="tabela-wrap"><table class="t fixa ord"><colgroup><col style="width:44px">{% if mostrar_depto and mostrar_acesso %}<col style="width:22%"><col style="width:20%"><col style="width:26%"><col>{% elif mostrar_depto %}<col style="width:30%"><col style="width:24%"><col>{% else %}<col style="width:34%"><col style="width:26%"><col>{% endif %}</colgroup>
<thead><tr><th class="chk"><span class="so-leitor">Selecionar</span></th>{{ cab('nome', 'Nome') }}{{ cab('login', 'Login') }}{% if mostrar_depto %}{{ cab('depto', 'Departamento') }}{% endif %}{% if mostrar_acesso %}<th>Acesso</th>{% endif %}</tr></thead><tbody>
{% for u in lista %}<tr><td class="chk">{% if not u.fora %}<input type="checkbox" name="login" value="{{ u.login }}" form="f-lista" aria-label="Selecionar {{ u.nome }}">{% endif %}</td><td data-v="{{ u.nome }}">{{ u.nome }}{% if not u.ativo %} <span class="tag">conta desativada</span>{% endif %}</td>
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
<p>Quem pode imprimir, por impressora, departamento e usuário. Para mudar um acesso, marque as pessoas, escolha o nível e monte a lista de alterações; nada muda no AD até você aplicar a lista com a sua senha.</p></div>

{% if aviso %}<div class="faixa {{ aviso[0] }}"><div class="ic">{{ ico('ok' if aviso[0] == 'ok' else 'aviso') }}</div>
<div><span>{{ aviso[1] }}</span></div></div>{% endif %}

{% if lote %}<section class="card lote">
<div class="cab-t"><h3>Resultado do lote de {{ lote.quando }}</h3>
<span class="pilula {{ 'falha' if lote.n_erro else 'ok' }}">{{ lote.n_ok }} alterada{{ '' if lote.n_ok == 1 else 's' }} · {{ lote.n_igual }} já {{ 'estava' if lote.n_igual == 1 else 'estavam' }} assim{% if lote.n_erro %} · {{ lote.n_erro }} com erro{% endif %}</span></div>
<div class="tabela-wrap"><table class="t"><thead><tr><th>Pessoa ou computador</th><th>Alteração</th><th>Resultado</th></tr></thead><tbody>
{% for it in lote.itens %}<tr><td>{{ it.nome }} <span class="sub-t">({{ it.login }})</span></td><td>{{ it.rotulo or '—' }}</td>
<td><span class="pilula {{ 'ok' if it.status == 'ok' else 'falha' if it.status == 'erro' else 'nd' }}">{{ 'Alterado' if it.status == 'ok' else 'Erro' if it.status == 'erro' else 'Já estava assim' }}</span>{% if it.msg and it.status == 'erro' %} <span class="sub-t">{{ it.msg }}</span>{% endif %}
{% for s in it.passos %}<div class="passo sub-t">{{ 'entrou em' if s.op == 'add' else 'saiu de' }} {{ s.grupo }}{% if s.res == 'erro' %} — falhou: {{ s.desc }}{% elif s.res == 'ja' %} (já estava){% endif %}</div>{% endfor %}</td></tr>
{% endfor %}</tbody></table></div>
<p class="rodape-card">O efeito não é imediato: o cache do winbind no servidor de impressão leva alguns minutos para enxergar os grupos, e a impressora aparece ou some no Windows no próximo logon da pessoa. Itens com erro continuam na lista para você tentar de novo.</p>
<form class="fecha" method="post" action="/permissoes/lote/fechar">{{ ocultos() }}<button class="btn-sec" type="submit">Fechar resultado</button></form></section>{% endif %}

{% if lista %}<section class="card lista-alt">
<div class="cab-t"><h3>Lista de alterações</h3>
<span class="pilula info">{{ lista|length }} {{ 'item' if lista|length == 1 else 'itens' }} · nada foi alterado ainda</span></div>
<div class="tabela-wrap"><table class="t"><thead><tr><th>Pessoa ou computador</th><th>Impressora</th><th>Agora</th><th>Depois</th><th></th></tr></thead><tbody>
{% for it in lista %}<tr><td>{{ it.nome }} <span class="sub-t">({{ it.login }})</span></td><td>{{ it.imp }}</td><td>{{ it.agora }}</td><td><b>{{ it.depois }}</b></td>
<td class="acoes-l"><form method="post" action="/permissoes/lista/remover">{{ ocultos() }}<input type="hidden" name="id" value="{{ it.id }}"><button class="mini" type="submit" aria-label="Tirar {{ it.nome }} da lista">Tirar</button></form></td></tr>
{% endfor %}</tbody></table></div>
{% if sug %}<div class="sug">
<div class="cab-t"><h3>Computadores dessas pessoas, segundo o GLPI</h3><span class="pilula info">sugestão: você confirma</span></div>
{% if sug.erro %}<p class="rodape-card">Não consegui consultar o GLPI agora ({{ sug.erro }}). A lista continua valendo: para liberar o computador de alguém, use a aba Computadores. {% if sug.novo %}O erro ficou registrado no log de auditoria.{% endif %}</p>
{% else %}
<form id="f-glpi" method="post" action="/permissoes/lista/pc-glpi">{{ ocultos() }}</form>
<div class="tabela-wrap"><table class="t"><thead><tr><th>Pessoa</th><th>Impressora</th><th>Computadores encontrados (último usuário logado)</th></tr></thead><tbody>
{% for l in sug.linhas %}<tr><td>{{ l.nome }} <span class="sub-t">({{ l.login }})</span></td><td>{{ l.imp }}</td><td>
{% for c in l.cands %}<label class="pc-op"><input type="checkbox" name="pc" value="{{ c.valor }}" form="f-glpi"{% if c.marcado %} checked{% endif %}{% if c.estado != 'livre' %} disabled{% endif %}> <span class="mono">{{ c.nome }}</span>
{% if c.estado == 'livre' %}<span class="sub-t">{{ c.entidade }}</span>
{% elif c.estado == 'liberado' %}<span class="pilula ok">já liberado</span>
{% elif c.estado == 'na_lista' %}<span class="pilula info">já está na lista</span>
{% elif c.estado == 'desativado' %}<span class="pilula nd">desativado no AD</span>
{% else %}<span class="pilula nd">não está no AD</span>{% endif %}</label>
{% else %}<span class="sub-t">Nenhum computador achado no GLPI com esse login. <a href="/permissoes?v=computadores&amp;p={{ l.imp_id }}">Procurar na aba Computadores</a>.</span>
{% endfor %}
{% if l.cands|length > 1 %}<div class="sub-t">{{ l.cands|length }} computadores com esse login: marque o que a pessoa usa.</div>{% endif %}
</td></tr>
{% endfor %}</tbody></table></div>
<div class="rodape-acao">{% if sug.n_livres %}<button class="btn-sec" type="submit" form="f-glpi">Liberar a impressora nos computadores marcados</button>
<span class="sub-t">Vão para a lista acima; nada muda no AD até você aplicar com a sua senha. A pessoa só imprime se o computador dela também estiver liberado.</span>{% else %}<span class="sub-t">Nenhum computador novo para liberar nesta lista.</span>{% endif %}</div>
{% endif %}</div>{% endif %}
<form class="aplicar" method="post" action="/permissoes/aplicar" autocomplete="off">{{ ocultos() }}
<div class="linha-form dois"><div class="campo"><label for="senha-aplicar">Senha de {{ nome_ator }} ({{ login_ator }}) para aplicar tudo de uma vez</label>
<input id="senha-aplicar" name="senha" type="password" required></div>
<button class="btn" type="submit">Aplicar {{ lista|length }} {{ 'alteração' if lista|length == 1 else 'alterações' }}</button></div></form>
<form class="esvazia" method="post" action="/permissoes/lista/limpar">{{ ocultos() }}<button class="btn-sec" type="submit">Esvaziar a lista</button></form>
</section>{% endif %}

{% if erro %}<div class="faixa erro"><div class="ic">{{ ico('aviso') }}</div>
<div><b>Não foi possível ler o AD</b><span>{{ erro }}</span></div></div>
{% else %}

{% if r.atencao %}<section class="estado atencao"><div class="sel">{{ ico('aviso') }}</div>
<div><h2>{{ r.atencao|length }} {{ 'ponto de atenção' if r.atencao|length == 1 else 'pontos de atenção' }}</h2>
<p>{{ r.atencao|join(' · ') }}</p></div></section>
{% else %}<section class="estado ok"><div class="sel">{{ ico('ok') }}</div>
<div><h2>Permissões em ordem</h2>
<p>{{ r.com_acesso }} pessoas com acesso a pelo menos uma das {{ imps|length }} {{ 'impressora' if imps|length == 1 else 'impressoras' }} e {{ r.pcs_filtro }} computadores liberados. Nenhuma conta desativada ou fora das OUs. Lido às {{ r.hora }}.</p></div></section>{% endif %}

<div class="fatos quatro">
<div class="card fato"><div class="rot">Impressoras</div><div class="val">{{ imps|length }}</div><div class="sub">cadastradas no painel</div></div>
<div class="card fato"><div class="rot">Pessoas com acesso</div><div class="val">{{ r.com_acesso }}</div><div class="sub">em pelo menos uma impressora</div></div>
<div class="card fato"><div class="rot">Computadores liberados</div><div class="val">{{ r.pcs_filtro }}</div><div class="sub">em pelo menos uma impressora</div></div>
<div class="card fato"><div class="rot">Usuários no AD</div><div class="val">{{ r.n_ativos }}</div><div class="sub">{{ r.n_deptos }} departamentos</div></div>
</div>

<nav class="abas" aria-label="Visões">
{% for k, rot in visoes %}<a href="/permissoes?v={{ k }}{% if k in ('impressora','computadores') %}&amp;p={{ p }}{% endif %}" class="{{ 'at' if k == v }}">{{ rot }}</a>{% endfor %}
<span class="esp"></span><a class="atualizar" href="/permissoes?v={{ v }}&amp;p={{ p }}{% if q %}&amp;q={{ q|urlencode }}{% endif %}&amp;r=1">Atualizar agora</a>
</nav>

{% if v in ('usuario', 'departamento', 'impressora') %}
<form id="f-lista" method="post" action="/permissoes/lista">{{ ocultos() }}</form>
<section class="card barra-acao"><div class="campo"><label for="alvo">Definir como</label>
<select id="alvo" name="alvo" form="f-lista" required><option value="" disabled selected>Escolha a impressora e o nível…</option>
{% for gp in alvos_sel %}<optgroup label="{{ gp.nome }}">{% for o in gp.opcoes %}<option value="{{ o.valor }}">{{ o.rotulo }}</option>{% endfor %}</optgroup>{% endfor %}</select></div>
<button class="btn" type="submit" form="f-lista">Adicionar à lista</button>
<p class="nota">Marque as pessoas nas tabelas abaixo e escolha o nível. Cada pessoa fica em um só grupo por impressora: entrar em um nível tira dos outros. Nada muda no AD até você aplicar a lista.</p></section>
{% endif %}

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
<form id="f-pc-del" method="post" action="/permissoes/lista/pc">{{ ocultos() }}<input type="hidden" name="acao" value="pc_del"></form>
<section class="card"><div class="cab-t"><h3>Computadores liberados em {{ f.nome }}</h3><span class="pilula ok">{{ x.pcs|length }}</span></div>
{% if x.pcs %}<div class="tabela-wrap"><table class="t fixa ord"><colgroup><col style="width:44px"><col style="width:52%"><col></colgroup><thead><tr><th class="chk"><span class="so-leitor">Selecionar</span></th>{{ cab('nome', 'Computador') }}{{ cab('depto', 'Departamento') }}</tr></thead><tbody>
{% for pc in x.pcs %}<tr><td class="chk">{% if not pc.fora %}<input type="checkbox" name="pc" value="{{ pc.nome }}" form="f-pc-del" aria-label="Selecionar {{ pc.nome }}">{% endif %}</td><td class="mono" data-v="{{ pc.nome }}">{{ pc.nome }}{% if not pc.ativo %} <span class="tag">desativado</span>{% endif %}</td><td data-v="{{ pc.depto }}">{{ pc.depto }}{% if pc.nivel_ou %} <span class="sub-t">› {{ pc.nivel_ou }}</span>{% endif %}</td></tr>
{% endfor %}</tbody></table></div>
<div class="rodape-acao"><button class="btn-sec" type="submit" form="f-pc-del">Retirar {{ f.nome }} dos marcados</button>
<span class="sub-t">Os marcados vão para a lista de alterações; nada muda até você aplicar com a sua senha.</span></div>
{% else %}<p class="rodape-card">Nenhum computador liberado nesta impressora (grupo {{ f.grupo_pcs }}).</p>{% endif %}</section>

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
{{ seletor('computadores', r.cont_sem, 'sem a impressora') }}
<form id="f-pc" method="post" action="/permissoes/lista/pc">{{ ocultos() }}<input type="hidden" name="acao" value="pc_add"></form>
<form id="f-pc-del" method="post" action="/permissoes/lista/pc">{{ ocultos() }}<input type="hidden" name="acao" value="pc_del"></form>
<section class="card"><form class="busca" method="get" action="/permissoes">
<input type="hidden" name="v" value="computadores"><input type="hidden" name="p" value="{{ p }}">
<input name="q" value="{{ q }}" placeholder="Buscar computador pelo nome (mínimo 2 letras)" maxlength="40" aria-label="Buscar computador">
<button class="btn" type="submit">Buscar</button></form>
{% if q and q|length < min_busca %}<p class="rodape-card">Digite pelo menos {{ min_busca }} letras.</p>
{% elif q and not r.achados_pc %}<p class="rodape-card">Nenhum computador encontrado para "{{ q }}".</p>
{% elif r.achados_pc %}<div class="tabela-wrap"><table class="t fixa ord"><colgroup><col style="width:44px"><col style="width:30%"><col style="width:30%"><col></colgroup><thead><tr><th class="chk"><span class="so-leitor">Selecionar</span></th>{{ cab('nome', 'Computador') }}{{ cab('depto', 'Departamento') }}<th>Situação em {{ sel.nome }}</th></tr></thead><tbody>
{% for pc in r.achados_pc %}<tr><td class="chk"><input type="checkbox" name="pc" value="{{ pc.nome }}" form="{{ 'f-pc-del' if pc.filtro[p] else 'f-pc' }}" aria-label="Selecionar {{ pc.nome }}"></td><td class="mono" data-v="{{ pc.nome }}">{{ pc.nome }}</td><td data-v="{{ pc.depto }}">{{ pc.depto }}{% if pc.nivel_ou %} <span class="sub-t">› {{ pc.nivel_ou }}</span>{% endif %}</td><td>{% if pc.filtro[p] %}<span class="pilula ok">liberado</span>{% else %}<span class="pilula nd">não liberado</span>{% endif %}</td></tr>
{% endfor %}</tbody></table></div>
{% if r.mais_pc %}<p class="rodape-card">Mostrando os {{ r.achados_pc|length }} primeiros. Refine a busca.</p>{% endif %}
{% else %}<p class="rodape-card">Busque pelo nome para achar o computador de alguém, ou abra um departamento abaixo.</p>{% endif %}</section>
<section class="card barra-acao"><button class="btn" type="submit" form="f-pc">Liberar {{ sel.nome }} nos marcados</button>
<button class="btn-sec" type="submit" form="f-pc-del">Retirar {{ sel.nome }} dos marcados</button>
<p class="nota">Marque os computadores nos resultados da busca: os não liberados entram com o primeiro botão, os já liberados saem com o segundo. Os marcados vão para a lista de alterações e nada muda até você aplicar a lista com a sua senha. Por trás, é o grupo {{ sel.grupo_pcs }} que a GPO usa para decidir em quais computadores essa impressora aparece.</p></section>
<section class="card"><div class="cab-t"><h3>Computadores ainda sem {{ sel.nome }}</h3>
<span class="pilula {{ 'ok' if not r.n_sem else 'atencao' }}">{{ r.n_sem }} de {{ r.n_pcs_total }}</span></div>
<p class="rodape-card nota-topo">Computadores das OUs de departamento que ainda não têm essa impressora liberada (não estão no grupo {{ sel.grupo_pcs }}, que a GPO usa para liberar). A OU Servidores não entra na conta.</p></section>
{% for d in r.pcs_deptos %}
<details class="card acao depto"><summary><div class="t"><b>{{ d.nome }}</b><span>{{ d.itens|length }} sem a impressora</span></div><div class="seta">{{ ico('seta') }}</div></summary>
<div class="tabela-wrap"><table class="t fixa"><colgroup><col style="width:44px"><col style="width:40%"><col></colgroup><thead><tr><th class="chk"><span class="so-leitor">Selecionar</span></th><th>Computador</th><th>Nível da OU</th></tr></thead><tbody>
{% for pc in d.itens %}<tr><td class="chk"><input type="checkbox" name="pc" value="{{ pc.nome }}" form="f-pc" aria-label="Selecionar {{ pc.nome }}"></td><td class="mono">{{ pc.nome }}</td><td>{{ pc.nivel_ou or '—' }}</td></tr>{% endfor %}</tbody></table></div></details>
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


def _busca_pcs(d, q):
    t = _k(q)
    achados = [p for p in _pcs_candidatos(d) if t in _k(p["nome"])]
    achados.sort(key=lambda p: _k(p["nome"]))
    return achados[:50], len(achados) > 50


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
  var n=idx(t,'nome');if(n<0)n=0;
  rows.sort(function(a,b){return col.compare(val(a,i),val(b,i))||col.compare(val(a,n),val(b,n));});
  rows.forEach(function(r){tb.appendChild(r);});
  t.querySelectorAll('thead th').forEach(function(th,j){th.setAttribute('aria-sort',j===i?'ascending':'none');});
 });
}
document.addEventListener('click',function(e){var b=e.target.closest&&e.target.closest('.ord-b');if(b)ordenar(b.getAttribute('data-k'));});
})();
"""


PROXY = "192.0.2.8"
AVISOS = {
    "senha": ("erro", "Senha incorreta. Nada foi alterado."),
    "bloqueado": ("erro", "Muitas tentativas. Aguarde alguns minutos. Nada foi alterado."),
    "ldap": ("erro", "Não foi possível falar com o servidor de domínio. Nada foi alterado."),
    "vazia": ("erro", "A lista de alterações está vazia."),
    "origem": ("erro", "Pedido recusado por segurança (origem diferente). Nada foi alterado."),
    "ad": ("erro", "Não foi possível ler o AD para validar as pessoas. Nada foi adicionado."),
    "sem_selecao": ("amarelo", "Marque pelo menos uma pessoa nas tabelas."),
    "sem_selecao_pc": ("amarelo", "Marque pelo menos um computador nas tabelas."),
    "alvo": ("amarelo", "Escolha a impressora e o nível em \"Definir como\"."),
}
MOTIVOS = {"nao": "usuário não encontrado", "desativada": "conta desativada", "cheia": "lista cheia",
           "pc_nao": "computador não encontrado", "pc_desativado": "computador desativado"}


def _origem():
    if request.remote_addr == PROXY:
        xff = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        if xff:
            return xff
    return request.remote_addr or "-"


def _origem_ok():
    """Defesa extra contra pedido vindo de outro site (alem do cookie SameSite=Strict)."""
    sf = request.headers.get("Sec-Fetch-Site")
    if sf is not None:
        return sf in ("same-origin", "none")
    org = request.headers.get("Origin")
    if org:
        return urlsplit(org).netloc == request.host
    return True


def _volta(**extra):
    v = request.form.get("v", "usuario")
    if v not in dict(VISOES):
        v = "usuario"
    params = {"v": v}
    q = request.form.get("q", "").strip()[:40]
    if q:
        params["q"] = q
    if request.form.get("p", "") in [i["id"] for i in REG.IMPRESSORAS]:
        params["p"] = request.form["p"]
    params.update(extra)
    return redirect("/permissoes?" + urlencode(params))


def _aviso(args):
    m = args.get("m", "")
    if m == "adicionado":
        try:
            n = max(0, min(int(args.get("n", "0")), 999))
            rej = max(0, min(int(args.get("rej", "0")), 999))
        except ValueError:
            return None
        pc = args.get("k") == "pc"
        quando = " para retirar a impressora" if args.get("a") == "del" else " para liberar a impressora"
        txt = (f"{n} {'computador adicionado' if n == 1 else 'computadores adicionados'} à lista{quando}." if pc else
               f"{n} {'pessoa adicionada' if n == 1 else 'pessoas adicionadas'} à lista.")
        if rej:
            txt += (f" {rej} {'ignorado' if (pc and rej == 1) else 'ignorada' if rej == 1 else 'ignorados' if pc else 'ignoradas'}"
                    + (f" ({MOTIVOS[args['rm']]})" if args.get("rm") in MOTIVOS else "") + ".")
        return ("ok" if n else "amarelo", txt)
    return AVISOS.get(m)


def _alvos_sel(imps):
    saida = []
    for p in imps:
        ops = [{"valor": f"{p['id']}:{n['id']}", "rotulo": n["rotulo"]} for n in p["niveis"]]
        ops.append({"valor": f"{p['id']}:{ESC.NENHUM}", "rotulo": "Sem acesso"})
        saida.append({"nome": f"{p['nome']} · {p['local']}", "opcoes": ops})
    return saida


def _lista_view(ator, d):
    por_login = {u["login"].lower(): u for u in d["usuarios"]} if d else {}
    por_pc = {m["nome"].lower(): m for m in d["pcs"]} if d else {}
    imps = {i["id"]: i for i in REG.IMPRESSORAS}
    saida = []
    for it in ESC.listar(ator):
        p = imps.get(it["impressora"])
        if it["nivel"] in ESC.PC_ACOES:
            nome = it["login"][len(ESC.PC_PREFIXO):]
            m = por_pc.get(nome.lower())
            no = m["filtro"].get(it["impressora"]) if m else None
            saida.append({"id": it["id"], "login": "computador", "nome": nome,
                          "imp": p["nome"] if p else it["impressora"],
                          "agora": "—" if no is None else ("Liberado" if no else "Não liberado"),
                          "depois": "Liberado" if it["nivel"] == ESC.PC_ADD else "Não liberado"})
            continue
        u = por_login.get(it["login"].lower())
        nivel = next((n for n in p["niveis"] if n["id"] == it["nivel"]), None) if p else None
        saida.append({"id": it["id"], "login": it["login"], "nome": u["nome"] if u else it["login"],
                      "imp": p["nome"] if p else it["impressora"],
                      "agora": ESC.nivel_atual(p, u["acesso"]) if (p and u) else "—",
                      "depois": nivel["rotulo"] if nivel else
                                ("Sem acesso" if it["nivel"] == ESC.NENHUM else "—")})
    return saida


def _sugestoes(ator, d, origem):
    """Computadores das pessoas que estao na lista (entrando em algum nivel), segundo o GLPI.
    So sugere: quem confirma e o administrador. Falha do GLPI nunca derruba a pagina."""
    if not d:
        return None
    itens = ESC.listar(ator)
    pedidos = [it for it in itens if not it["login"].startswith(ESC.PC_PREFIXO) and it["nivel"] != ESC.NENHUM]
    if not pedidos:
        return None
    try:
        achados = GLPI.computadores_de([it["login"] for it in pedidos])
    except GLPI.ErroGLPI as e:
        if e.novo:
            auth.auditar("erro_glpi", ator, origem, str(e)[:120])
        return {"erro": str(e), "novo": e.novo, "linhas": [], "n_livres": 0}
    por_login = {u["login"].lower(): u for u in d["usuarios"]}
    por_pc = {m["nome"].lower(): m for m in d["pcs"] if not m.get("fora")}
    imps = {i["id"]: i for i in REG.IMPRESSORAS}
    na_lista = {(it["impressora"], it["login"][len(ESC.PC_PREFIXO):].lower())
                for it in itens if it["login"].startswith(ESC.PC_PREFIXO) and it["nivel"] == ESC.PC_ADD}
    linhas, n_livres = [], 0
    for it in pedidos:
        p = imps.get(it["impressora"])
        if p is None:
            continue
        u = por_login.get(it["login"].lower())
        cands = []
        for pc in achados.get(it["login"].lower(), []):
            m = por_pc.get(pc["nome"].lower())
            if m is None:
                estado = "sem_ad"
            elif not m["ativo"]:
                estado = "desativado"
            elif m["filtro"].get(p["id"]):
                estado = "liberado"
            elif (p["id"], m["nome"].lower()) in na_lista:
                estado = "na_lista"
            else:
                estado = "livre"
            nome = m["nome"] if m else pc["nome"]
            cands.append({"nome": nome, "estado": estado, "entidade": pc["entidade"],
                          "valor": f"{p['id']}|{nome}"})
        # so vem marcado quando nao ha duvida: um unico computador achado e ainda nao liberado
        for c in cands:
            c["marcado"] = len(cands) == 1 and c["estado"] == "livre"
        n_livres += sum(1 for c in cands if c["estado"] == "livre")
        linhas.append({"nome": u["nome"] if u else it["login"], "login": it["login"],
                       "imp": p["nome"], "imp_id": p["id"], "cands": cands})
    return {"erro": None, "novo": False, "linhas": linhas, "n_livres": n_livres}


def _lote_view(ator, d):
    lote = ESC.ler_lote(ator)
    if lote:
        por_login = {u["login"].lower(): u for u in d["usuarios"]} if d else {}
        for it in lote["itens"]:
            if it["login"].startswith(ESC.PC_PREFIXO):
                it["nome"], it["login"] = it["login"][len(ESC.PC_PREFIXO):], "computador"
                continue
            u = por_login.get(it["login"].lower())
            it["nome"] = u["nome"] if u else it["login"]
    return lote


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
        d = None
        if request.args.get("r") == "1":
            GLPI.limpar_cache()
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
                r["achados_pc"], r["mais_pc"] = (_busca_pcs(d, q) if len(q) >= MIN_BUSCA else ([], False))
            dados["r"] = r
        niv = {i["id"]: {n["id"]: n for n in i["niveis"]} for i in imps}
        ator = g.sess["usuario"]
        return pagina("Permissões de impressão", CORPO, "per", v=v, q=q, p=p, sel=sel, visoes=VISOES,
                      imps=imps, niv=niv, min_busca=MIN_BUSCA, alvos_sel=_alvos_sel(imps),
                      lista=_lista_view(ator, d), lote=_lote_view(ator, d), sug=_sugestoes(ator, d, _origem()),
                      aviso=_aviso(request.args), nome_ator=g.sess["nome"], login_ator=ator, **dados)

    def _recusa_origem():
        if _origem_ok():
            return None
        auth.auditar("pedido_recusado", g.sess["usuario"], _origem(), request.path + " origem")
        return _volta(m="origem")

    @app.post("/permissoes/lista")
    @requer("ti")
    def lista_adicionar():
        r = _recusa_origem()
        if r:
            return r
        u, o = g.sess["usuario"], _origem()
        alvo = request.form.get("alvo", "")
        if alvo not in ESC.alvos():
            return _volta(m="alvo")
        logins = [x.strip() for x in request.form.getlist("login")][:200]
        if not logins:
            return _volta(m="sem_selecao")
        try:
            d = AD.carregar()
        except AD.ErroAD:
            return _volta(m="ad")
        n, rej = ESC.adicionar(u, logins, alvo, d)
        auth.auditar("lista_adicionada", u, o, f"alvo={alvo} itens={n} rejeitados={len(rej)}")
        extra = {"m": "adicionado", "n": n}
        if rej:
            extra["rej"] = len(rej)
            motivo = rej[0][1]
            extra["rm"] = ("desativada" if motivo.startswith("conta") else
                           "cheia" if motivo.startswith("lista") else "nao")
        return _volta(**extra)

    @app.post("/permissoes/lista/pc")
    @requer("ti")
    def lista_pc():
        r = _recusa_origem()
        if r:
            return r
        u, o = g.sess["usuario"], _origem()
        acao = request.form.get("acao", "")
        imp = request.form.get("p", "")
        if acao not in ESC.PC_ACOES or imp not in [i["id"] for i in REG.IMPRESSORAS]:
            return _volta(m="alvo")
        nomes = [x.strip() for x in request.form.getlist("pc")][:200]
        if not nomes:
            return _volta(m="sem_selecao_pc")
        try:
            d = AD.carregar()
        except AD.ErroAD:
            return _volta(m="ad")
        n, rej = ESC.adicionar_pcs(u, nomes, imp, acao, d)
        auth.auditar("lista_adicionada", u, o, f"alvo={imp}:{acao} itens={n} rejeitados={len(rej)}")
        extra = {"m": "adicionado", "n": n, "k": "pc", "a": "del" if acao == ESC.PC_DEL else "add"}
        if rej:
            extra["rej"] = len(rej)
            motivo = rej[0][1]
            extra["rm"] = ("pc_desativado" if "desativado" in motivo else
                           "cheia" if motivo.startswith("lista") else "pc_nao")
        return _volta(**extra)

    @app.post("/permissoes/lista/pc-glpi")
    @requer("ti")
    def lista_pc_glpi():
        """Computadores marcados no bloco de sugestoes do GLPI: entram na MESMA lista (liberar a impressora)."""
        r = _recusa_origem()
        if r:
            return r
        u, o = g.sess["usuario"], _origem()
        ids = [i["id"] for i in REG.IMPRESSORAS]
        por_imp = {}
        for valor in request.form.getlist("pc")[:200]:
            imp, _, nome = valor.partition("|")
            if imp in ids and nome.strip():
                por_imp.setdefault(imp, []).append(nome.strip())
        if not por_imp:
            return _volta(m="sem_selecao_pc")
        try:
            d = AD.carregar()
        except AD.ErroAD:
            return _volta(m="ad")
        n, rej, motivo = 0, 0, ""
        for imp, nomes in por_imp.items():
            e, rj = ESC.adicionar_pcs(u, nomes, imp, ESC.PC_ADD, d)
            n += e
            rej += len(rj)
            motivo = motivo or (rj[0][1] if rj else "")
            auth.auditar("lista_adicionada", u, o, f"alvo={imp}:{ESC.PC_ADD} itens={e} rejeitados={len(rj)} via=glpi")
        extra = {"m": "adicionado", "n": n, "k": "pc", "a": "add"}
        if rej:
            extra["rej"] = rej
            extra["rm"] = ("pc_desativado" if "desativado" in motivo else
                           "cheia" if motivo.startswith("lista") else "pc_nao")
        return _volta(**extra)

    @app.post("/permissoes/lista/remover")
    @requer("ti")
    def lista_remover():
        r = _recusa_origem()
        if r:
            return r
        try:
            item = int(request.form.get("id", ""))
        except ValueError:
            return _volta()
        ESC.remover(g.sess["usuario"], item)
        auth.auditar("lista_item_removido", g.sess["usuario"], _origem(), f"item={item}")
        return _volta()

    @app.post("/permissoes/lista/limpar")
    @requer("ti")
    def lista_limpar():
        r = _recusa_origem()
        if r:
            return r
        ESC.limpar(g.sess["usuario"])
        auth.auditar("lista_esvaziada", g.sess["usuario"], _origem())
        return _volta()

    @app.post("/permissoes/lote/fechar")
    @requer("ti")
    def lote_fechar():
        r = _recusa_origem()
        if r:
            return r
        ESC.fechar_lote(g.sess["usuario"])
        return _volta()

    @app.post("/permissoes/aplicar")
    @requer("ti")
    def lista_aplicar():
        r = _recusa_origem()
        if r:
            return r
        lote, codigo = ESC.aplicar(g.sess["usuario"], request.form.get("senha", ""), _origem())
        if lote is None:
            return _volta(m=codigo)
        try:
            AD.carregar(forcar=True)          # a pagina ja mostra o estado novo
        except AD.ErroAD:
            pass
        return _volta()
