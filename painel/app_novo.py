"""Painel de Impressoes (EMPRESA): login, sair e as 3 paginas."""
import os
from datetime import datetime
from functools import wraps

from flask import (Flask, abort, jsonify, make_response, redirect,
                   render_template_string, request, g)

import auth
import visual

app = Flask(__name__)
visual.registrar(app)

COOKIE = "painel_sessao"
COOKIE_SEGURO = os.environ.get("PAINEL_COOKIE_SEGURO", "1") == "1"
PROXY = "192.0.2.8"

IMPRESSORA = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" '
              'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
              '<path d="M7 9V4h10v5"/><rect x="3.5" y="9" width="17" height="8" rx="2"/>'
              '<path d="M7 14h10v6H7z"/></svg>')
ALERTA = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" '
          'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
          '<path d="M12 4l9.5 16.5h-19z"/><path d="M12 10.5v4M12 17.6v.01"/></svg>')

BASE = """<!doctype html>
<html lang="pt-BR" data-logado="{{ '1' if sess else '0' }}"><head><meta charset="utf-8">
<script src="/guarda.js"></script>
<meta name="viewport" content="width=device-width, initial-scale=1">
{% if refresh %}<meta http-equiv="refresh" content="{{ refresh }}">{% endif %}
<title>{{ titulo }} - Painel de Impressões</title>
<link rel="stylesheet" href="/estilo.css">
</head><body>
{% if sess %}<header class="topo"><div class="in">
<div class="marca">{{ impressora|safe }}<span>Painel de Impressões</span></div>
<nav>
{% if 'gestor' in sess.papeis %}<a href="/impressoes" class="{{ 'at' if pag=='imp' }}">Impressões</a>{% endif %}
{% if 'ti' in sess.papeis %}<a href="/permissoes" class="{{ 'at' if pag=='per' }}">Permissões</a>
<a href="/winbind" class="{{ 'at' if pag=='win' }}">Winbind</a>{% endif %}
</nav><span class="esp"></span>
<div class="usuario"><span class="quem">{{ sess.nome }}</span>
<form id="form-sair" method="post" action="/sair"><button class="btn-sair" type="submit">Sair</button></form></div>
</div></header>{% endif %}
{{ corpo|safe }}
</body></html>"""

LOGIN = """<div class="login-wrap"><form class="card caixa-login" method="post" action="/login"
id="form-login" autocomplete="off">
<div class="logo"><div class="sel">{{ impressora|safe }}</div><h1>Painel de Impressões</h1></div>
<p class="sub">Entre com seu usuário e senha do domínio.</p>
{% if msg %}<div class="faixa {{ tipo }}"><div class="ic">{{ alerta|safe }}</div><div><span>{{ msg }}</span></div></div>{% endif %}
<div><label for="usuario">Usuário do domínio</label>
<input id="usuario" name="usuario" autofocus required maxlength="40" autocapitalize="none" spellcheck="false"></div>
<div><label for="senha">Senha</label><input id="senha" name="senha" type="password" required></div>
<button class="btn" type="submit">Entrar</button>
<div class="rodape">Acesso restrito e registrado em auditoria. A sessão expira após
10 minutos sem atividade.</div></form></div>"""

PAGINA = """<div class="pagina"><div class="cab"><h1>{{ titulo }}</h1><p>{{ desc }}</p></div>
<section class="card vazio"><p>Em construção.</p></section></div>"""

NEGADO = """<div class="pagina"><div class="cab"><h1>Acesso negado</h1>
<p>Você não tem permissão para esta página.</p></div></div>"""


def pagina(titulo, corpo_tpl, pag="", refresh=None, **kw):
    corpo = render_template_string(corpo_tpl, titulo=titulo, **kw)
    return render_template_string(BASE, titulo=titulo, corpo=corpo, pag=pag, refresh=refresh,
                                 impressora=IMPRESSORA, sess=getattr(g, "sess", None))


def tela_login(msg=None, tipo="erro", status=200):
    corpo = render_template_string(LOGIN, msg=msg, tipo=tipo, impressora=IMPRESSORA,
                                   alerta=ALERTA)
    html = render_template_string(BASE, titulo="Entrar", sess=None, pag="", refresh=None,
                                  impressora=IMPRESSORA, corpo=corpo)
    return make_response(html, status)


def origem():
    if request.remote_addr == PROXY:
        xff = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        if xff:
            return xff
    return request.remote_addr or "-"


def requer(papel):
    def deco(f):
        @wraps(f)
        def w(*a, **k):
            if not g.sess:
                return redirect("/login")
            if papel not in g.sess["papeis"]:
                auth.auditar("acesso_negado", g.sess["usuario"], origem(), request.path)
                abort(403)
            return f(*a, **k)
        return w
    return deco


@app.before_request
def carregar_sessao():
    g.sess = auth.sessao(request.cookies.get(COOKIE))


@app.after_request
def cabecalhos(r):
    r.headers["Cache-Control"] = "no-store"
    r.headers["X-Frame-Options"] = "DENY"
    r.headers["X-Content-Type-Options"] = "nosniff"
    r.headers["Referrer-Policy"] = "same-origin"
    r.headers["Content-Security-Policy"] = ("default-src 'self'; style-src 'self' "
                                            "'unsafe-inline'; form-action 'self'")
    return r


@app.errorhandler(403)
def negado(_e):
    return pagina("Acesso negado", NEGADO), 403


GUARDA_JS = """(function(){
var K='painel_aba';
function marcar(){try{sessionStorage.setItem(K,'1')}catch(e){}}
function limpar(){try{sessionStorage.removeItem(K)}catch(e){}}
document.addEventListener('DOMContentLoaded',function(){
 var f=document.getElementById('form-login');
 if(f){f.addEventListener('submit',marcar);}
 var s=document.getElementById('form-sair');
 if(s){s.addEventListener('submit',limpar);}
});
if(document.documentElement.getAttribute('data-logado')==='1'){
 var ok=false;try{ok=sessionStorage.getItem(K)==='1'}catch(e){}
 if(!ok){
  document.documentElement.style.display='none';
  fetch('/sair',{method:'POST',credentials:'same-origin'})
   .catch(function(){}).then(function(){location.replace('/login?m=aba')});
 }
}
})();
"""


@app.get("/guarda.js")
def guarda_js():
    r = make_response(GUARDA_JS)
    r.headers["Content-Type"] = "application/javascript; charset=utf-8"
    return r


@app.get("/saude")
def saude():
    return jsonify(status="ok", hora=datetime.now().isoformat(timespec="seconds"))


@app.get("/")
def inicio():
    if not g.sess:
        return redirect("/login")
    return redirect("/impressoes" if "gestor" in g.sess["papeis"] else "/login")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        if request.args.get("m") == "aba":
            return tela_login("Por segurança, a sessão não continua depois de fechar a "
                              "janela. Entre novamente.", "amarelo")
        return tela_login()
    token, msg = auth.autenticar(request.form.get("usuario", ""),
                                 request.form.get("senha", ""), origem())
    if not token:
        return tela_login(msg, "erro", 401)
    r = redirect("/")
    # cookie de sessao: sem Max-Age/Expires, o navegador descarta ao fechar
    r.set_cookie(COOKIE, token, httponly=True, secure=COOKIE_SEGURO,
                 samesite="Strict", path="/")
    return r


@app.post("/sair")
def sair():
    if g.sess:
        auth.auditar("logout", g.sess["usuario"], origem())
    auth.encerrar(request.cookies.get(COOKIE))
    r = redirect("/login")
    r.delete_cookie(COOKIE, path="/")
    return r


@app.get("/impressoes")
@requer("gestor")
def p_impressoes():
    return pagina("Controle de impressões", PAGINA, "imp",
                  desc="Totais por impressora, usuário e mês.")


import pag_winbind  # noqa: E402

pag_winbind.registrar(app, requer, pagina)

import pag_permissoes  # noqa: E402

pag_permissoes.registrar(app, requer, pagina)

import pag_carrossel  # noqa: E402

pag_carrossel.registrar(app, origem)
