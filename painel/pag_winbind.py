"""Pagina 3 do painel: situacao do winbind e botao de troca controlada."""
import json
import subprocess
import time
from datetime import datetime, timedelta

from flask import g, make_response, redirect, request

import auth

ARQ_STATUS = "/var/lib/troca-senha-maquina/status.json"
ATRASO_MAX_S = 2 * 3600   # verificacao roda de hora em hora
UNIT = "troca-senha-maquina.service"
SYSTEMCTL = "/usr/bin/systemctl"
PROXY = "192.0.2.8"
RODANDO = {"activating", "active", "reloading"}
DIAS_SEMANA = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
               "sexta-feira", "sábado", "domingo"]
AVISO_AMARELO_DIAS = 7     # faixa amarela a partir de 7 dias antes
AVISO_LARANJA_DIAS = 2     # faixa laranja a partir de 2 dias antes
MAX_DIAS_SEM_TROCA = 35    # acima disso: vermelho
ATRASO_TROCA_H = 6         # tolerancia depois das 04:00 da troca agendada
ESPERA_INICIO_S = 45       # depois do clique, aguarda a troca por ate 45 s

MENSAGENS = {
    "confirmacao": ("erro", "Digite exatamente TROCAR para confirmar."),
    "senha": ("erro", "Senha incorreta. Nada foi feito."),
    "bloqueado": ("erro", "Muitas tentativas. Aguarde alguns minutos."),
    "ldap": ("erro", "Não foi possível falar com o servidor de domínio. Nada foi feito."),
    "andamento": ("erro", "Já existe uma troca em andamento."),
    "erro": ("erro", "Não foi possível iniciar a troca. Avise a TI (ver auditoria)."),
}

CORPO = """
{% macro ico(n) -%}
{%- if n == 'ok' -%}<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg>
{%- elif n == 'aviso' -%}<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 4l9.5 16.5h-19z"/><path d="M12 10.5v4M12 17.6v.01"/></svg>
{%- elif n == 'x' -%}<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"/></svg>
{%- elif n == 'relogio' -%}<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/></svg>
{%- elif n == 'seta' -%}<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M6 9l6 6 6-6"/></svg>
{%- endif -%}
{%- endmacro %}
<div class="pagina">
<div class="cab"><h1>{{ titulo }}</h1>
<p>Senha da conta de máquina SRV-CUPS e leitura de grupos pelo filtro de impressão.</p></div>

{% if aviso %}<div class="faixa {{ aviso[0] }}"><div class="ic">{{ ico('ok' if aviso[0] == 'ok' else 'aviso') }}</div>
<div><span>{{ aviso[1] }}</span></div></div>{% endif %}

{% if alerta %}<div class="faixa {{ alerta[0] }}"><div class="ic">{{ ico('aviso' if alerta[0] == 'vermelho' else 'relogio') }}</div>
<div><b>{{ alerta[1] }}</b><span>{{ alerta[2] }}</span></div></div>{% endif %}

<section class="estado {{ estado.classe }}"><div class="sel">{{ ico(estado.icone) }}</div>
<div><h2>{{ estado.titulo }}</h2><p>{{ estado.sub }}</p></div></section>

{% if not erro %}
<div class="fatos">
<div class="card fato"><div class="rot">Senha trocada em</div>
<div class="val">{{ fatos.troca_data }}</div><div class="sub">{{ fatos.troca_rel }}</div></div>
<div class="card fato"><div class="rot">Próxima troca</div>
<div class="val">{{ fatos.prox_data }}</div><div class="sub">{{ fatos.prox_sub }}</div></div>
<div class="card fato"><div class="rot">Última troca</div>
<div class="val"><span class="pilula {{ fatos.res_classe }}">{{ fatos.res_texto }}</span></div>
<div class="sub">{{ fatos.exec_txt }}</div></div>
</div>

{% if ciclo %}<section class="card ciclo">
<div class="topo-c"><span class="rot">Ciclo da senha</span><span class="dia">Dia {{ ciclo.dia }} de {{ ciclo.total }}</span></div>
<div class="trilho"><div class="cheio {{ ciclo.nivel }}" style="width:{{ ciclo.pct }}%"></div><div class="hoje" style="left:{{ ciclo.pct }}%"></div></div>
<div class="pontas"><span>{{ ciclo.ini }}</span><span>{{ ciclo.fim }}</span></div>
</section>{% endif %}

<section class="card testes"><div class="cab-t"><h3>Testes da última verificação</h3>
<span class="pilula {{ 'ok' if testes_ok == testes|length else 'falha' }}">{{ testes_ok }} de {{ testes|length }} ok</span></div>
{% for t in testes %}<div class="teste"><div class="bolha {{ '' if t.ok else 'nao' }}">{{ ico('ok' if t.ok else 'x') }}</div>
<div>{{ t.nome }}</div><div class="det">{{ t.detalhe }}</div></div>
{% endfor %}</section>
{% endif %}

{% if rodando %}
<section class="card andamento"><b>Troca em andamento…</b>
<span class="nota">Trocando a senha e reiniciando o winbind. Leva cerca de 10 segundos; esta página atualiza sozinha.</span>
<div class="barra"><i></i></div></section>
{% else %}
<details class="card acao" {{ 'open' if abrir }}>
<summary><div class="t"><b>Trocar a senha da máquina agora</b>
<span>Reinicia o winbind por alguns segundos. Evite durante impressões em massa.</span></div>
<div class="seta">{{ ico('seta') }}</div></summary>
<form class="corpo" method="post" action="/winbind/trocar" autocomplete="off">
<p class="nota">A troca automática continua marcada para a primeira segunda-feira do mês, às 04:00.</p>
<div class="linha-form">
<div class="campo"><label for="senha">Senha de {{ nome }} ({{ login }})</label>
<input id="senha" name="senha" type="password" required></div>
<div class="campo"><label for="confirmacao">Digite TROCAR</label>
<input id="confirmacao" name="confirmacao" required autocomplete="off" maxlength="10"></div>
<button class="btn" type="submit">Trocar agora</button></div>
</form></details>
{% endif %}
</div>"""


def agora():
    return datetime.now()


def _dt(valor):
    try:
        return datetime.fromisoformat(str(valor))
    except (TypeError, ValueError):
        return None


def fmt(valor):
    """2026-10-19T15:07:17 -> 19/10/2026 15:07 (se nao der, devolve o texto)."""
    if valor in (None, ""):
        return "—"
    d = _dt(valor)
    return d.strftime("%d/%m/%Y %H:%M") if d else str(valor)


def primeira_segunda(ano, mes):
    d = datetime(ano, mes, 1, 4, 0)
    return d + timedelta(days=(7 - d.weekday()) % 7)


def _proxima_troca(ref):
    """Proxima primeira segunda-feira, 04:00, depois de ref."""
    ano, mes = ref.year, ref.month
    for _ in range(3):
        d = primeira_segunda(ano, mes)
        if d > ref:
            return d
        ano, mes = (ano + 1, 1) if mes == 12 else (ano, mes + 1)
    return d


def _ultima_agendada(ref):
    """Ultima primeira segunda-feira, 04:00, ja ocorrida ate ref."""
    ano, mes = ref.year, ref.month
    for _ in range(3):
        d = primeira_segunda(ano, mes)
        if d <= ref:
            return d
        ano, mes = (ano - 1, 12) if mes == 1 else (ano, mes - 1)
    return d


def _quando(dt, ref):
    n = (dt.date() - ref.date()).days
    return "hoje" if n == 0 else "amanhã" if n == 1 else f"em {n} dias"


def _ha(dt, ref):
    n = (ref.date() - dt.date()).days
    return "hoje" if n <= 0 else "ontem" if n == 1 else f"há {n} dias"


def _idade(seg):
    if seg < 90:
        return "agora há pouco"
    if seg < 3600:
        return f"há {int(seg // 60)} min"
    return f"há {int(seg // 3600)} h"


def alerta_prazo(s, ref):
    """Aviso sobre a troca. Devolve (nivel, titulo, texto) ou None."""
    ultima_ad = _dt(s.get("ultima_troca_ad"))
    # 1) vermelho: troca agendada que nao aconteceu
    prev = _ultima_agendada(ref)
    if (ref > prev + timedelta(hours=ATRASO_TROCA_H) and ultima_ad
            and ultima_ad < prev):
        return ("vermelho", "A troca automática não aconteceu",
                f"Era esperada em {prev:%d/%m/%Y %H:%M}; a última troca da senha foi em "
                f"{fmt(s.get('ultima_troca_ad'))}. Verifique o agendador "
                "(troca-senha-maquina.timer) ou use o botão abaixo.")
    # 2) vermelho: senha velha demais
    dias = s.get("dias_desde_troca")
    if isinstance(dias, (int, float)) and dias > MAX_DIAS_SEM_TROCA:
        return ("vermelho", f"Senha da máquina sem troca há {int(dias)} dias",
                f"O limite é de {MAX_DIAS_SEM_TROCA} dias. Faça a troca pelo botão abaixo.")
    # 3) aviso por proximidade
    prox = _dt(s.get("proxima_troca"))
    if not prox or prox <= ref:
        prox = _proxima_troca(ref)
    n = (prox.date() - ref.date()).days
    if n > AVISO_AMARELO_DIAS:
        return None
    nivel = "laranja" if n <= AVISO_LARANJA_DIAS else "amarelo"
    dia = f"{DIAS_SEMANA[prox.weekday()]}, {prox:%d/%m} às {prox:%H:%M}"
    return (nivel, f"Troca automática da senha {_quando(prox, ref)}",
            f"{dia}. O winbind reinicia por alguns segundos. "
            "Esteja disponível para conferir logo cedo.")


def _origem():
    if request.remote_addr == PROXY:
        xff = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        if xff:
            return xff
    return request.remote_addr or "-"


def _estado():
    try:
        r = subprocess.run([SYSTEMCTL, "show", "-p", "ActiveState", "--value", UNIT],
                           capture_output=True, text=True, timeout=5)
        return r.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return "desconhecido"


def _ler():
    with open(ARQ_STATUS, encoding="utf-8") as f:
        return json.load(f)


def montar():
    """Devolve dict com tudo que a pagina mostra."""
    ref = agora()
    try:
        s = _ler()
    except (OSError, ValueError):
        return {"erro": True, "alerta": None, "ult_exec_dt": None, "res_troca": None,
                "estado": {"classe": "falha", "icone": "x",
                           "titulo": "Status indisponível",
                           "sub": "Não foi possível ler o status do winbind. Avise a TI."}}
    testes = s.get("testes", [])
    testes_ok = sum(1 for t in testes if t.get("ok"))
    gerado = _dt(s.get("gerado_em"))
    idade = (ref - gerado).total_seconds() if gerado else None
    hora = f"{gerado:%H:%M}" if gerado else "—"
    if s.get("resultado") != "ok":
        estado = {"classe": "falha", "icone": "x", "titulo": "Falha na última verificação",
                  "sub": f"Verificado às {hora}. {len(testes) - testes_ok} de {len(testes)} "
                         "testes falharam; veja a lista abaixo."}
    elif idade is None or idade > ATRASO_MAX_S:
        estado = {"classe": "atencao", "icone": "aviso", "titulo": "Verificação atrasada",
                  "sub": f"A última verificação foi às {hora}"
                         + (f" ({_idade(idade)})" if idade is not None else "")
                         + ". Ela deveria rodar de hora em hora."}
    else:
        estado = {"classe": "ok", "icone": "ok", "titulo": "Winbind funcionando",
                  "sub": f"Verificado às {hora} ({_idade(idade)}). "
                         f"{testes_ok} de {len(testes)} testes passaram."}

    ultima_ad = _dt(s.get("ultima_troca_ad"))
    prox = _dt(s.get("proxima_troca"))
    if not prox or prox <= ref:
        prox = _proxima_troca(ref)
    alerta = alerta_prazo(s, ref)
    res = s.get("ultimo_resultado_trocar")
    fatos = {
        "troca_data": fmt(s.get("ultima_troca_ad")),
        "troca_rel": _ha(ultima_ad, ref) if ultima_ad else "sem registro",
        "prox_data": f"{prox:%d/%m/%Y %H:%M}",
        "prox_sub": f"{DIAS_SEMANA[prox.weekday()]} · {_quando(prox, ref)}",
        "res_classe": "ok" if res == "ok" else "falha" if res else "nd",
        "res_texto": "Concluída com sucesso" if res == "ok" else "Falhou" if res else "Sem registro",
        "exec_txt": "Executada em " + fmt(s.get("ultima_execucao_trocar")),
    }
    ciclo = None
    if ultima_ad and prox > ultima_ad:
        total = (prox - ultima_ad).total_seconds()
        pct = max(0.0, min(100.0, (ref - ultima_ad).total_seconds() / total * 100))
        ciclo = {"pct": f"{pct:.1f}", "nivel": alerta[0] if alerta else "ok",
                 "dia": (ref.date() - ultima_ad.date()).days + 1,
                 "total": (prox.date() - ultima_ad.date()).days,
                 "ini": f"{ultima_ad:%d/%m}", "fim": f"{prox:%d/%m}"}
    return {"erro": False, "estado": estado, "fatos": fatos, "ciclo": ciclo,
            "testes": testes, "testes_ok": testes_ok, "alerta": alerta,
            "ult_exec_dt": _dt(s.get("ultima_execucao_trocar")), "res_troca": res}


def _desde(param):
    try:
        return datetime.fromtimestamp(int(param))
    except (TypeError, ValueError, OverflowError, OSError):
        return None


def registrar(app, requer, pagina):
    @app.get("/winbind")
    @requer("ti")
    def p_winbind():
        ref = agora()
        rodando = _estado() in RODANDO
        dados = montar()
        m = request.args.get("m", "")
        aviso = MENSAGENS.get(m)
        if m == "iniciada":
            aviso = None
            desde = _desde(request.args.get("t"))
            if desde and 0 <= (ref - desde).total_seconds() < 600:
                ult = dados.get("ult_exec_dt")
                terminou = ult is not None and ult >= desde - timedelta(seconds=3)
                if not rodando and not terminou and (ref - desde).total_seconds() < ESPERA_INICIO_S:
                    rodando = True       # o systemd ainda nao marcou a unit
                elif not rodando and terminou:
                    ok = dados.get("res_troca") == "ok"
                    aviso = ("ok", "Troca concluída com sucesso." if ok else
                             "A troca terminou com falha. Veja o log da troca no servidor.")
        html = pagina("Controle do winbind", CORPO, "win",
                      refresh=3 if rodando else None, rodando=rodando, aviso=aviso,
                      abrir=bool(aviso and aviso[0] == "erro"),
                      nome=g.sess["nome"], login=g.sess["usuario"], **dados)
        return make_response(html)

    @app.post("/winbind/trocar")
    @requer("ti")
    def trocar():
        u, o = g.sess["usuario"], _origem()
        if request.form.get("confirmacao", "").strip() != "TROCAR":
            auth.auditar("troca_recusada", u, o, "confirmacao")
            return redirect("/winbind?m=confirmacao")
        if _estado() in RODANDO:
            auth.auditar("troca_recusada", u, o, "ja em andamento")
            return redirect("/winbind?m=andamento")
        ok, codigo = auth.reautenticar(u, request.form.get("senha", ""), o)
        if not ok:
            auth.auditar("troca_recusada", u, o, "reautenticacao: " + codigo)
            return redirect("/winbind?m=" + codigo)
        try:
            r = subprocess.run([SYSTEMCTL, "start", "--no-block", UNIT],
                               capture_output=True, text=True, timeout=10)
            falhou = r.returncode != 0
            detalhe = (r.stderr or "").strip()[:200]
        except (OSError, subprocess.SubprocessError) as e:
            falhou, detalhe = True, type(e).__name__
        if falhou:
            auth.auditar("troca_erro", u, o, detalhe)
            return redirect("/winbind?m=erro")
        auth.auditar("troca_solicitada", u, o)
        return redirect(f"/winbind?m=iniciada&t={int(time.time())}")
