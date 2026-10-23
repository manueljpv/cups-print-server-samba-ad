"""Autenticacao do painel: login LDAPS direto no DC, sessoes e limite de tentativas.

- Login = bind LDAPS com a propria senha do usuario (nada de senha guardada).
- Sessoes e tentativas ficam num SQLite compartilhado entre os workers.
- O cookie guarda so um token aleatorio; o banco guarda o HMAC dele.
"""
import hashlib
import hmac
import json
import re
import secrets
import sqlite3
import ssl
import time
from datetime import datetime

from ldap3 import Connection, SIMPLE, Server, Tls
from ldap3.core.exceptions import LDAPException
from ldap3.utils.conv import escape_filter_chars

DC = "dc01.empresa.local"
DOMINIO = "empresa.local"
BASE = "DC=empresa,DC=local"
CA = "/etc/painel-impressao/ca-dc.pem"
ARQ_CHAVE = "/etc/painel-impressao/chave-sessao"
DB = "/var/lib/painel-impressao/painel.db"
ARQ_AUDITORIA = "/var/lib/painel-impressao/auditoria.log"

GRUPO_TI = "painel_admin_ti"
GRUPOS_GESTORES = {"relatorio_impressao"}

MAX_ERROS = 5
BLOQUEIO_S = 300
OCIOSIDADE_S = 600       # 10 min sem atividade
MAXIMO_S = 8 * 3600      # teto absoluto da sessao

_LOGIN_OK = re.compile(r"^[A-Za-z0-9._-]{1,40}$")


def _chave():
    with open(ARQ_CHAVE, "rb") as f:
        return f.read().strip()


def _db():
    con = sqlite3.connect(DB, timeout=10)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("CREATE TABLE IF NOT EXISTS tentativas ("
                "chave TEXT PRIMARY KEY, falhas INTEGER, ate REAL, ultima REAL)")
    con.execute("CREATE TABLE IF NOT EXISTS sessoes ("
                "hash TEXT PRIMARY KEY, usuario TEXT, nome TEXT, grupos TEXT, "
                "criada REAL, ultima REAL)")
    con.execute("CREATE TABLE IF NOT EXISTS lista_alteracoes ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, ator TEXT, impressora TEXT, "
                "login TEXT, nivel TEXT, criado REAL, UNIQUE(ator, impressora, login))")
    con.execute("CREATE TABLE IF NOT EXISTS ultimo_lote ("
                "ator TEXT PRIMARY KEY, json TEXT, quando REAL)")
    return con


def _hash(token):
    return hmac.new(_chave(), token.encode(), hashlib.sha256).hexdigest()


def auditar(evento, usuario="-", origem="-", detalhe=""):
    linha = {"quando": datetime.now().isoformat(timespec="seconds"),
             "evento": evento, "usuario": usuario, "origem": origem,
             "detalhe": detalhe}
    with open(ARQ_AUDITORIA, "a", encoding="utf-8") as f:
        f.write(json.dumps(linha, ensure_ascii=False) + "\n")


# ---------- limite de tentativas ----------

def _chaves(usuario, origem):
    return ["u:" + usuario.lower(), "ip:" + origem]


def bloqueado(usuario, origem):
    """Devolve segundos restantes de bloqueio (0 = liberado)."""
    agora = time.time()
    restante = 0
    con = _db()
    try:
        for ch in _chaves(usuario, origem):
            lin = con.execute("SELECT ate FROM tentativas WHERE chave=?", (ch,)).fetchone()
            if lin and lin[0] and lin[0] > agora:
                restante = max(restante, int(lin[0] - agora) + 1)
    finally:
        con.close()
    return restante


def _registrar_falha(usuario, origem):
    agora = time.time()
    con = _db()
    try:
        for ch in _chaves(usuario, origem):
            lin = con.execute("SELECT falhas, ate, ultima FROM tentativas WHERE chave=?",
                              (ch,)).fetchone()
            falhas = 0
            # falhas antigas (mais de BLOQUEIO_S atras) deixam de contar
            if lin and lin[2] and agora - lin[2] < BLOQUEIO_S:
                falhas = lin[0]
            falhas += 1
            ate = agora + BLOQUEIO_S if falhas >= MAX_ERROS else 0
            if ate:
                falhas = 0
            con.execute("INSERT OR REPLACE INTO tentativas VALUES (?,?,?,?)",
                        (ch, falhas, ate, agora))
        con.commit()
    finally:
        con.close()


def _limpar_falhas(usuario, origem):
    con = _db()
    try:
        for ch in _chaves(usuario, origem):
            con.execute("DELETE FROM tentativas WHERE chave=?", (ch,))
        con.commit()
    finally:
        con.close()


# ---------- LDAPS ----------

def _cn(dn):
    m = re.match(r"^CN=((?:\\.|[^,\\])+)", dn, re.IGNORECASE)
    return m.group(1).lower() if m else ""


def _ldap_login(usuario, senha):
    """Bind com a senha do usuario; devolve (nome, [grupos]) ou None."""
    tls = Tls(validate=ssl.CERT_REQUIRED, version=ssl.PROTOCOL_TLS_CLIENT,
              ca_certs_file=CA)
    srv = Server(DC, port=636, use_ssl=True, tls=tls, connect_timeout=5)
    con = Connection(srv, user=f"{usuario}@{DOMINIO}", password=senha,
                     authentication=SIMPLE, receive_timeout=8, raise_exceptions=False)
    try:
        if not con.bind():
            return None
        con.search(BASE, f"(sAMAccountName={escape_filter_chars(usuario)})",
                   attributes=["memberOf", "displayName"])
        if not con.entries:
            return None
        e = con.entries[0]
        grupos = sorted({_cn(str(g)) for g in e.memberOf.values})
        nome = str(e.displayName.value) if e.displayName.value else usuario
        return nome, grupos
    finally:
        try:
            con.unbind()
        except Exception:
            pass


def papeis(grupos):
    """Traduz grupos do AD em papeis do painel."""
    p = set()
    if GRUPO_TI in grupos:
        p.update({"ti", "gestor"})
    if GRUPOS_GESTORES & set(grupos):
        p.add("gestor")
    return sorted(p)


def autenticar(usuario, senha, origem):
    """Devolve (token, None) em caso de sucesso ou (None, mensagem)."""
    usuario = (usuario or "").strip()
    if not _LOGIN_OK.match(usuario) or not senha:
        auditar("login_recusado", usuario[:40], origem, "formato invalido")
        return None, "Usuário ou senha inválidos."
    resto = bloqueado(usuario, origem)
    if resto:
        auditar("login_bloqueado", usuario, origem, f"{resto}s restantes")
        return None, f"Muitas tentativas. Aguarde {resto // 60 + 1} min."
    try:
        res = _ldap_login(usuario, senha)
    except (LDAPException, OSError, ssl.SSLError) as e:
        auditar("erro_ldap", usuario, origem, type(e).__name__)
        return None, "Não foi possível falar com o servidor de domínio. Avise a TI."
    if res is None:
        _registrar_falha(usuario, origem)
        auditar("login_falhou", usuario, origem)
        return None, "Usuário ou senha inválidos."
    nome, grupos = res
    pp = papeis(grupos)
    if not pp:
        # senha certa, mas sem grupo do painel: nao conta como falha de senha
        auditar("login_sem_permissao", usuario, origem)
        return None, "Você não tem permissão para acessar este painel."
    _limpar_falhas(usuario, origem)
    token = secrets.token_urlsafe(32)
    agora = time.time()
    con = _db()
    try:
        con.execute("INSERT INTO sessoes VALUES (?,?,?,?,?,?)",
                    (_hash(token), usuario.lower(), nome, ",".join(pp), agora, agora))
        # lista de alteracoes e resultado de lote nao atravessam logins
        con.execute("DELETE FROM lista_alteracoes WHERE ator=?", (usuario.lower(),))
        con.execute("DELETE FROM ultimo_lote WHERE ator=?", (usuario.lower(),))
        con.execute("DELETE FROM sessoes WHERE ultima < ?", (agora - MAXIMO_S,))
        con.commit()
    finally:
        con.close()
    auditar("login_ok", usuario, origem, ",".join(pp))
    return token, None


# ---------- sessao ----------

def sessao(token):
    """Valida o token e renova a atividade. Devolve dict ou None."""
    if not token:
        return None
    h = _hash(token)
    agora = time.time()
    con = _db()
    try:
        lin = con.execute("SELECT usuario, nome, grupos, criada, ultima "
                          "FROM sessoes WHERE hash=?", (h,)).fetchone()
        if not lin:
            return None
        usuario, nome, pp, criada, ultima = lin
        if agora - ultima > OCIOSIDADE_S or agora - criada > MAXIMO_S:
            con.execute("DELETE FROM sessoes WHERE hash=?", (h,))
            con.commit()
            return None
        con.execute("UPDATE sessoes SET ultima=? WHERE hash=?", (agora, h))
        con.commit()
        return {"usuario": usuario, "nome": nome, "papeis": set(pp.split(","))}
    finally:
        con.close()


def encerrar(token):
    if not token:
        return
    h = _hash(token)
    con = _db()
    try:
        lin = con.execute("SELECT usuario FROM sessoes WHERE hash=?", (h,)).fetchone()
        if lin:
            con.execute("DELETE FROM lista_alteracoes WHERE ator=?", (lin[0],))
            con.execute("DELETE FROM ultimo_lote WHERE ator=?", (lin[0],))
        con.execute("DELETE FROM sessoes WHERE hash=?", (h,))
        con.commit()
    finally:
        con.close()


# ---------- reautenticacao (acoes sensiveis) ----------

def reautenticar(usuario, senha, origem):
    """Confere de novo a senha de quem ja esta logado, sem criar sessao.

    Devolve (True, None) ou (False, codigo), codigo em: senha, bloqueado, ldap.
    Conta nas mesmas tentativas do login (5 erros bloqueiam 5 min).
    """
    if not senha:
        return False, "senha"
    resto = bloqueado(usuario, origem)
    if resto:
        auditar("reauth_bloqueado", usuario, origem, f"{resto}s restantes")
        return False, "bloqueado"
    try:
        res = _ldap_login(usuario, senha)
    except (LDAPException, OSError, ssl.SSLError) as e:
        auditar("erro_ldap", usuario, origem, type(e).__name__)
        return False, "ldap"
    if res is None or "ti" not in papeis(res[1]):
        _registrar_falha(usuario, origem)
        auditar("reauth_falhou", usuario, origem)
        return False, "senha"
    _limpar_falhas(usuario, origem)
    return True, None


# ---------- escrita no AD com a conta de quem esta logado ----------

def conexao_usuario(usuario, senha, origem):
    """Abre uma conexao LDAPS com a senha de quem esta logado, para ESCREVER no AD.

    Devolve (conexao, None) ou (None, codigo), codigo em: senha, bloqueado, ldap.
    Quem chama e responsavel por fechar (unbind). A senha nao e guardada em lugar nenhum.
    Conta nas mesmas tentativas do login (5 erros bloqueiam 5 min). Exige o papel TI.
    """
    if not senha:
        return None, "senha"
    resto = bloqueado(usuario, origem)
    if resto:
        auditar("reauth_bloqueado", usuario, origem, f"{resto}s restantes")
        return None, "bloqueado"
    con = None
    try:
        tls = Tls(validate=ssl.CERT_REQUIRED, version=ssl.PROTOCOL_TLS_CLIENT, ca_certs_file=CA)
        srv = Server(DC, port=636, use_ssl=True, tls=tls, connect_timeout=5)
        con = Connection(srv, user=f"{usuario}@{DOMINIO}", password=senha,
                         authentication=SIMPLE, receive_timeout=15, raise_exceptions=False)
        if not con.bind():
            _registrar_falha(usuario, origem)
            auditar("reauth_falhou", usuario, origem)
            return None, "senha"
        con.search(BASE, f"(sAMAccountName={escape_filter_chars(usuario)})",
                   attributes=["memberOf"])
        if not con.entries:
            _registrar_falha(usuario, origem)
            auditar("reauth_falhou", usuario, origem)
            _fechar(con)
            return None, "senha"
        grupos = sorted({_cn(str(g)) for g in con.entries[0].memberOf.values})
        if "ti" not in papeis(grupos):
            _registrar_falha(usuario, origem)
            auditar("reauth_falhou", usuario, origem, "sem papel ti")
            _fechar(con)
            return None, "senha"
    except (LDAPException, OSError, ssl.SSLError) as e:
        auditar("erro_ldap", usuario, origem, type(e).__name__)
        _fechar(con)
        return None, "ldap"
    _limpar_falhas(usuario, origem)
    return con, None


def _fechar(con):
    if con is None:
        return
    try:
        con.unbind()
    except Exception:
        pass
