"""Leitura (somente leitura) do AD para a pagina de permissoes.

Usa a conta svc-painel-leitura (usuario comum, sem escrita) por LDAPS, com a CA validada.
Guarda o resultado em memoria por CACHE_S segundos para nao consultar o DC a cada clique.
"""
import re
import ssl
import threading
import time

from ldap3 import Connection, SIMPLE, Server, Tls
from ldap3.core.exceptions import LDAPException

DC = "dc01.empresa.local"
DOMINIO = "empresa.local"
CONTA = "svc-painel-leitura"
CA = "/etc/painel-impressao/ca-dc.pem"
ARQ_SENHA = "/etc/painel-impressao/senha-leitura"
BASE_RAIZ = "OU=EMPRESA,DC=empresa,DC=local"
BASE_USUARIOS = "OU=users,OU=EMPRESA,DC=empresa,DC=local"
CACHE_S = 60

import impressoras as REG

_OU = re.compile(r"OU=((?:\\.|[^,\\])+)", re.IGNORECASE)
_CN = re.compile(r"^CN=((?:\\.|[^,\\])+)", re.IGNORECASE)


class ErroAD(Exception):
    """Falha ao ler o AD (rede, certificado, senha ou permissao)."""


def _um(v):
    if isinstance(v, (list, tuple)):
        v = v[0] if v else ""
    return "" if v is None else str(v)


def _lista(v):
    if v is None or v == "":
        return []
    if isinstance(v, (list, tuple)):
        return [str(x) for x in v]
    return [str(v)]


def _cn(dn):
    m = _CN.match(dn)
    return m.group(1).lower() if m else ""


def _ous(dn, raiz):
    """OUs do DN da folha para a raiz, sem a raiz (users/computadores) e sem 'EMPRESA'."""
    partes = [p.replace("\\,", ",") for p in _OU.findall(dn)]
    partes = [p for p in partes if p.lower() != "empresa"]
    if raiz in [p.lower() for p in partes]:
        partes = partes[:[p.lower() for p in partes].index(raiz)]
    return partes


def _ler(con, base, filtro, attrs):
    saida = []
    for r in con.extend.standard.paged_search(base, filtro, attributes=attrs,
                                              paged_size=500, generator=True):
        if r.get("type") != "searchResEntry":
            continue
        a = r["attributes"]
        saida.append({"dn": r["dn"], **{k: a.get(k) for k in attrs}})
    return saida


def _buscar():
    """Devolve (usuarios, computadores, grupos) crus do LDAP."""
    try:
        with open(ARQ_SENHA, "r", encoding="utf-8") as f:
            senha = f.read().strip("\r\n")
        tls = Tls(validate=ssl.CERT_REQUIRED, version=ssl.PROTOCOL_TLS_CLIENT, ca_certs_file=CA)
        srv = Server(DC, port=636, use_ssl=True, tls=tls, connect_timeout=5)
        con = Connection(srv, user=f"{CONTA}@{DOMINIO}", password=senha,
                         authentication=SIMPLE, receive_timeout=15, raise_exceptions=False)
        if not con.bind():
            raise ErroAD("bind recusado")
        try:
            usuarios = _ler(con, BASE_USUARIOS,
                            "(&(objectClass=user)(!(objectClass=computer)))",
                            ["sAMAccountName", "displayName", "userAccountControl", "memberOf"])
            pcs = _ler(con, BASE_RAIZ, "(objectClass=computer)",
                       ["name", "userAccountControl", "memberOf"])
            filtro_g = "(&(objectClass=group)(|" + "".join(
                f"(cn={g})" for g in sorted(nomes_grupos())) + "))"
            grupos = {}
            for g in _ler(con, "DC=empresa,DC=local", filtro_g, ["cn", "member"]):
                grupos[_um(g.get("cn")).lower()] = _lista(g.get("member"))
        finally:
            try:
                con.unbind()
            except Exception:
                pass
    except (LDAPException, OSError, ssl.SSLError) as e:
        raise ErroAD(type(e).__name__) from e
    return usuarios, pcs, grupos


def nomes_grupos(imps=None):
    """Todos os grupos citados no cadastro de impressoras (nomes originais)."""
    nomes = set()
    for p in (imps if imps is not None else REG.IMPRESSORAS):
        nomes.add(p["grupo_pcs"])
        nomes.update(n["grupo"] for n in p["niveis"])
    return nomes


def _montar(usuarios, pcs, grupos=None, imps=None):
    imps = imps if imps is not None else REG.IMPRESSORAS
    gente, maquinas = [], []

    def acesso_de(gset):
        res = {}
        for p in imps:
            res[p["id"]] = next((n["id"] for n in p["niveis"] if n["grupo"].lower() in gset), None)
        return res

    def filtro_de(gset):
        return {p["id"]: p["grupo_pcs"].lower() in gset for p in imps}

    for e in usuarios:
        login = _um(e.get("sAMAccountName"))
        if not login:
            continue
        gset = {_cn(g) for g in _lista(e.get("memberOf"))}
        ous = _ous(e["dn"], "users")
        uac = int(_um(e.get("userAccountControl")) or 0)
        gente.append({"login": login, "nome": _um(e.get("displayName")) or login,
                      "depto": ous[-1] if ous else "(sem OU de departamento)",
                      "sub": " › ".join(reversed(ous[:-1])), "acesso": acesso_de(gset),
                      "ativo": not (uac & 2)})
    for e in pcs:
        nome = _um(e.get("name"))
        if not nome:
            continue
        gset = {_cn(g) for g in _lista(e.get("memberOf"))}
        ous = _ous(e["dn"], "computadores")
        uac = int(_um(e.get("userAccountControl")) or 0)
        dentro = "computadores" in [x.lower() for x in _OU.findall(e["dn"])]
        maquinas.append({"nome": nome, "depto": ous[-1] if (ous and dentro) else "(fora das OUs de departamento)",
                         "nivel_ou": ous[0] if len(ous) > 1 and dentro else "",
                         "filtro": filtro_de(gset), "ativo": not (uac & 2)})
    # membros de grupo que nao estao em OU=users nem nas OUs de computadores (ou sao grupos aninhados)
    vistos = {e["dn"].lower() for e in usuarios} | {e["dn"].lower() for e in pcs}
    tem_grupos = grupos is not None
    grupos = grupos or {}
    extras = {}
    for p in imps:
        for n in p["niveis"]:
            for dn in grupos.get(n["grupo"].lower(), []):
                if dn.lower() not in vistos:
                    ex = extras.setdefault(dn.lower(), _extra(dn, imps))
                    # guarda o nivel mais alto (niveis vem do maior para o menor)
                    if ex["acesso"][p["id"]] is None:
                        ex["acesso"][p["id"]] = n["id"]
        for dn in grupos.get(p["grupo_pcs"].lower(), []):
            if dn.lower() not in vistos:
                extras.setdefault(dn.lower(), _extra(dn, imps))["filtro"][p["id"]] = True
    fora = "(fora das OUs de departamento)"
    for ex in extras.values():
        if any(ex["acesso"].values()):
            gente.append({"login": ex["nome"], "nome": ex["nome"], "depto": fora, "sub": "",
                          "acesso": ex["acesso"], "ativo": True, "fora": True})
        if any(ex["filtro"].values()):
            maquinas.append({"nome": ex["nome"], "depto": fora, "nivel_ou": "",
                             "filtro": ex["filtro"], "ativo": True, "fora": True})
    # grupos citados no cadastro que nao existem no AD
    ausentes = sorted(n for n in nomes_grupos(imps) if n.lower() not in grupos) if tem_grupos else []
    return {"usuarios": gente, "pcs": maquinas, "quando": time.time(), "grupos_ausentes": ausentes}


def _extra(dn, imps):
    nome = _CN.match(dn).group(1).replace("\\,", ",") if _CN.match(dn) else dn
    return {"nome": nome, "acesso": {p["id"]: None for p in imps}, "filtro": {p["id"]: False for p in imps}}


_cache = {"t": 0.0, "d": None}
_trava = threading.Lock()


def carregar(forcar=False):
    with _trava:
        if not forcar and _cache["d"] and time.time() - _cache["t"] < CACHE_S:
            return _cache["d"]
        d = _montar(*_buscar())
        _cache["t"], _cache["d"] = time.time(), d
        return d
