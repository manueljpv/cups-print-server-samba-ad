"""Consulta ao GLPI (SOMENTE LEITURA): sugere os computadores de um usuario.

Regra de ligacao: o campo "Nome alternativo do usuario" do computador (preenchido pelo GLPI Agent
com o ultimo usuario logado, no formato login@EMPRESA). O login e o texto antes do "@", sem diferenciar
maiusculas de minusculas. O painel so SUGERE; quem confirma ou troca e o administrador, e nada e
gravado no GLPI.

Credenciais: /etc/painel-impressao/glpi.env (root:painel, 640) com GLPI_APP_TOKEN e GLPI_USER_TOKEN.
O usuario da API (svc-cups-glpi) tem perfil que so le Computadores. Os tokens nunca vao para
log, auditoria ou tela. A conexao vai direto ao IP interno do GLPI, validando o certificado
pelo nome publico (SNI), porque o nome publico resolve para fora da rede.
"""
import http.client
import json
import re
import socket
import ssl
import threading
import time
import urllib.parse

HOST = "glpi.empresa.local"
IP = "192.0.2.108"
ARQ_CONF = "/etc/painel-impressao/glpi.env"
CAMPO_NOME, CAMPO_CONTATO, CAMPO_ENTIDADE = 1, 7, 80      # opcoes de busca de Computer no GLPI
TIMEOUT_S = 5            # o painel nao pode travar se o GLPI estiver lento
CACHE_S = 300            # resposta por login
FALHA_S = 60             # depois de uma falha nao tenta de novo por este tempo
LIMITE = 20              # maximo de computadores por login
LOGIN_OK = re.compile(r"^[A-Za-z0-9._-]{1,40}$")

_trava = threading.Lock()
_cache = {}              # login minusculo -> (instante, [computadores])
_falha = {"ate": 0.0, "msg": ""}


class ErroGLPI(Exception):
    """Falha ao consultar o GLPI. `novo` e True na primeira falha (as seguintes vem do cache de falha)."""

    def __init__(self, msg, novo=True):
        super().__init__(msg)
        self.novo = novo


def limpar_cache():
    with _trava:
        _cache.clear()
        _falha.update({"ate": 0.0, "msg": ""})


def _conf():
    try:
        dados = {}
        with open(ARQ_CONF, encoding="utf-8") as f:
            for linha in f:
                if "=" in linha and not linha.lstrip().startswith("#"):
                    k, v = linha.rstrip("\r\n").split("=", 1)
                    dados[k.strip()] = v.strip()
    except OSError:
        raise ErroGLPI("arquivo de credenciais do GLPI ilegivel")
    if not dados.get("GLPI_APP_TOKEN") or not dados.get("GLPI_USER_TOKEN"):
        raise ErroGLPI("credenciais do GLPI incompletas")
    return dados


def _conexao():
    """HTTPS direto ao IP interno, com o nome publico no TLS (certificado validado)."""
    ctx = ssl.create_default_context()
    s = ctx.wrap_socket(socket.create_connection((IP, 443), timeout=TIMEOUT_S), server_hostname=HOST)
    con = http.client.HTTPSConnection(HOST, context=ctx, timeout=TIMEOUT_S)
    con.sock = s
    return con


def _get(con, conf, caminho, cab=None):
    h = {"App-Token": conf["GLPI_APP_TOKEN"]}
    h.update(cab or {})
    con.request("GET", caminho, headers=h)
    r = con.getresponse()
    corpo = r.read()
    if r.status not in (200, 206):
        raise ErroGLPI(f"GLPI respondeu HTTP {r.status}")
    try:
        return json.loads(corpo) if corpo else None
    except ValueError:
        raise ErroGLPI("resposta do GLPI ilegivel")


def _buscar_login(con, conf, sessao, login):
    q = urllib.parse.urlencode({
        "criteria[0][field]": CAMPO_CONTATO, "criteria[0][searchtype]": "contains",
        "criteria[0][value]": login,
        "forcedisplay[0]": CAMPO_NOME, "forcedisplay[1]": CAMPO_CONTATO, "forcedisplay[2]": CAMPO_ENTIDADE,
        "range": f"0-{LIMITE - 1}"})
    d = _get(con, conf, "/apirest.php/search/Computer?" + q, {"Session-Token": sessao}) or {}
    achados, vistos = [], set()
    for linha in d.get("data") or []:
        nome = str(linha.get(str(CAMPO_NOME)) or "").strip()
        contato = str(linha.get(str(CAMPO_CONTATO)) or "").strip()
        if not nome or nome.lower() in vistos:
            continue
        if contato.split("@")[0].strip().lower() != login.lower():     # casamento exato (a busca e por trecho)
            continue
        vistos.add(nome.lower())
        achados.append({"nome": nome, "contato": contato,
                        "entidade": str(linha.get(str(CAMPO_ENTIDADE)) or "").strip()})
    achados.sort(key=lambda x: x["nome"].lower())
    return achados


def computadores_de(logins):
    """{login_minusculo: [{nome, contato, entidade}]} para os logins pedidos. Levanta ErroGLPI."""
    pedidos = []
    for lg in dict.fromkeys(logins):
        if LOGIN_OK.match(lg or ""):
            pedidos.append(lg.lower())
    agora = time.time()
    with _trava:
        faltam = [lg for lg in pedidos if lg not in _cache or agora - _cache[lg][0] >= CACHE_S]
        if faltam and agora < _falha["ate"]:
            raise ErroGLPI(_falha["msg"], novo=False)
        if faltam:
            try:
                novos = _consultar(faltam)
            except ErroGLPI as e:
                _falha.update({"ate": time.time() + FALHA_S, "msg": str(e)})
                raise
            except (OSError, ssl.SSLError, http.client.HTTPException) as e:
                msg = f"falha de rede ao falar com o GLPI ({type(e).__name__})"
                _falha.update({"ate": time.time() + FALHA_S, "msg": msg})
                raise ErroGLPI(msg)
            for lg, lista in novos.items():
                _cache[lg] = (time.time(), lista)
        return {lg: list(_cache[lg][1]) for lg in pedidos}


def _consultar(logins):
    conf = _conf()
    con = _conexao()
    sessao = None
    try:
        d = _get(con, conf, "/apirest.php/initSession", {"Authorization": "user_token " + conf["GLPI_USER_TOKEN"]})
        sessao = (d or {}).get("session_token")
        if not sessao:
            raise ErroGLPI("o GLPI nao abriu a sessao")
        return {lg: _buscar_login(con, conf, sessao, lg) for lg in logins}
    finally:
        try:
            if sessao:
                _get(con, conf, "/apirest.php/killSession", {"Session-Token": sessao})
        except Exception:
            pass
        try:
            con.close()
        except Exception:
            pass
