"""Pagina do carrossel (TV): status do winbind em tela cheia, sem login, so para o mini PC."""
from datetime import timedelta

from flask import abort, make_response, render_template_string, request

import pag_winbind as W

IPS_PERMITIDOS = {"192.0.2.96"}   # mini PC tv-kiosk-carousel

TEMAS = {   # nivel: (fundo, texto, painel dos blocos)
    "ok":       ("#12703a", "#ffffff", "rgba(0,0,0,.20)"),
    "amarelo":  ("#f5c400", "#1f1700", "rgba(255,255,255,.38)"),
    "laranja":  ("#b84f00", "#ffffff", "rgba(0,0,0,.22)"),
    "vermelho": ("#c62828", "#ffffff", "rgba(0,0,0,.24)"),
}

ICONES = {
    "ok": '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
    "relogio": '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>',
    "aviso": '<path d="M12 4l9.5 16.5h-19z"/><path d="M12 10.5v4M12 17.6v.01"/>',
    "x": '<path d="M6 6l12 12M18 6L6 18"/>',
}

PAGINA = """<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Winbind - SRV-CUPS</title>
<style>
*{box-sizing:border-box}
html,body{margin:0;height:100%}
body{background:{{ t[0] }};color:{{ t[1] }};font-family:system-ui,"Segoe UI",Roboto,Arial,sans-serif;
 -webkit-font-smoothing:antialiased;overflow:hidden}
.tela{height:100vh;display:grid;grid-template-rows:auto 1fr auto auto;gap:2.6vh;padding:4vh 4vw}
.topo{display:flex;justify-content:space-between;font-size:2.4vh;letter-spacing:.12em;
 text-transform:uppercase;font-weight:650;opacity:.85}
.centro{display:grid;grid-template-columns:auto 1fr;gap:3.5vw;align-items:center}
.sel{width:21vh;height:21vh;border-radius:50%;background:{{ t[1] }};color:{{ t[0] }};display:grid;place-items:center}
.sel svg{width:62%;height:62%;fill:none;stroke:currentColor;stroke-width:2.4;stroke-linecap:round;stroke-linejoin:round}
h1{margin:0;font-size:8.6vh;line-height:1.05;letter-spacing:-.02em;text-wrap:balance}
.sub{margin:1.6vh 0 0;font-size:3.6vh;line-height:1.3;opacity:.92}
.blocos{display:grid;grid-template-columns:repeat(4,1fr);gap:1.6vw}
.bloco{background:{{ t[2] }};border-radius:2vh;padding:2.4vh 1.6vw}
.rot{font-size:2.1vh;letter-spacing:.1em;text-transform:uppercase;font-weight:650;opacity:.8}
.val{font-size:4.8vh;font-weight:750;margin-top:.8vh;font-variant-numeric:tabular-nums;line-height:1.1}
.nota{font-size:2.5vh;margin-top:.6vh;opacity:.9}
.acao{background:{{ t[1] }};color:{{ t[0] }};border-radius:2vh;padding:2.4vh 2vw;font-size:3.6vh;font-weight:700;
 display:flex;gap:1.6vw;align-items:center}
.acao small{font-size:2.1vh;letter-spacing:.1em;text-transform:uppercase;font-weight:700;opacity:.75}
</style></head><body>
<main class="tela">
<div class="topo"><span>Winbind · SRV-CUPS</span><span>Verificado às {{ hora }}</span></div>
<section class="centro"><div class="sel"><svg viewBox="0 0 24 24" aria-hidden="true">{{ icone|safe }}</svg></div>
<div><h1>{{ titulo }}</h1><p class="sub">{{ sub }}</p></div></section>
<section class="blocos">
{% for b in blocos %}<div class="bloco"><div class="rot">{{ b[0] }}</div><div class="val">{{ b[1] }}</div><div class="nota">{{ b[2] }}</div></div>
{% endfor %}</section>
<section class="acao"><small>Ação</small><span>{{ acao }}</span></section>
</main></body></html>"""


def montar():
    """Escolhe o nivel (o pior entre estado e prazo) e monta os textos da TV."""
    ref = W.agora()
    try:
        s = W._ler()
    except (OSError, ValueError):
        return dict(nivel="vermelho", icone="x", titulo="Status do winbind indisponível",
                    sub="Não foi possível ler o arquivo de status.", hora="—", blocos=[
                        ("Última troca", "—", ""), ("Próxima troca", "—", ""),
                        ("Último teste", "—", ""), ("Sem trocar há", "—", "")],
                    acao="Avise a TI: o status do winbind não pode ser lido.")
    testes = s.get("testes", [])
    ok_n = sum(1 for t in testes if t.get("ok"))
    gerado = W._dt(s.get("gerado_em"))
    idade = (ref - gerado).total_seconds() if gerado else None
    hora = f"{gerado:%H:%M}" if gerado else "—"
    alerta = W.alerta_prazo(s, ref)
    ultima = W._dt(s.get("ultima_troca_ok")) or W._dt(s.get("ultima_troca_ad"))
    prox = W._dt(s.get("proxima_troca"))
    if not prox or prox <= ref:
        prox = W._proxima_troca(ref)
    dias = (ref.date() - ultima.date()).days if ultima else None

    if s.get("resultado") != "ok":
        nivel, icone = "vermelho", "x"
        titulo = "Winbind com falha"
        sub = f"{len(testes) - ok_n} de {len(testes)} testes falharam na última verificação."
        acao = "Abra impressoes.empresa.local › Winbind e veja os testes que falharam."
    elif idade is None or idade > W.ATRASO_MAX_S:
        nivel, icone = "amarelo", "aviso"
        titulo = "Verificação atrasada"
        sub = "A verificação de hora em hora não atualizou o status."
        acao = "Avise a TI: conferir o timer de verificação no srv-cups."
    elif alerta and alerta[0] == "vermelho":
        nivel, icone = "vermelho", "aviso"
        titulo = alerta[1]
        sub = (f"A última troca da senha foi em {ultima:%d/%m/%Y}." if ultima else "Sem registro de troca.")
        acao = "Faça a troca agora: impressoes.empresa.local › Winbind › Trocar agora."
    elif alerta:
        nivel, icone = alerta[0], "relogio"
        n = (prox.date() - ref.date()).days
        titulo = f"Troca da senha {W._quando(prox, ref)}"
        sub = f"{W.DIAS_SEMANA[prox.weekday()]}, {prox:%d/%m} às {prox:%H:%M}. O winbind reinicia por alguns segundos."
        acao = ("Esteja disponível na troca e confira o painel logo depois." if n <= W.AVISO_LARANJA_DIAS
                else "Nenhuma ação agora. A troca automática está próxima.")
    else:
        nivel, icone = "ok", "ok"
        titulo = "Winbind funcionando"
        sub = f"{ok_n} de {len(testes)} testes passaram na última verificação."
        acao = "Nenhuma ação necessária."

    blocos = [
        ("Última troca", f"{ultima:%d/%m %H:%M}" if ultima else "—",
         W._ha(ultima, ref) if ultima else "sem registro"),
        ("Próxima troca", f"{prox:%d/%m %H:%M}", f"{W.DIAS_SEMANA[prox.weekday()]} · {W._quando(prox, ref)}"),
        ("Último teste", f"{ok_n} de {len(testes)} OK", W._idade(idade) if idade is not None else ""),
        ("Sem trocar há", "—" if dias is None else f"{dias} dia" + ("" if dias == 1 else "s"),
         f"limite {W.MAX_DIAS_SEM_TROCA} dias"),
    ]
    return dict(nivel=nivel, icone=icone, titulo=titulo, sub=sub, hora=hora, blocos=blocos, acao=acao)


def registrar(app, origem):
    @app.get("/carrossel/winbind")
    def carrossel_winbind():
        if origem() not in IPS_PERMITIDOS:
            abort(404)      # para os demais, a rota nem parece existir
        d = montar()
        svg = ICONES[d.pop("icone")]
        html = render_template_string(PAGINA, t=TEMAS[d["nivel"]], icone=svg, **d)
        return make_response(html)
