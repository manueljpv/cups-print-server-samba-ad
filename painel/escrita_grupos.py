"""Pagina 2, etapas 2a e 2b: lista de alteracoes e escrita nos grupos Impressora_* do AD.

2a = pessoas nos grupos de nivel; 2b = computadores no grupo _PCs (filtro da GPO). Os itens de
computador usam login "pc:NOME" e nivel "pc_add" (incluir no filtro) ou "pc_del" (tirar do filtro).

- A escrita usa a CONEXAO LDAPS DE QUEM ESTA LOGADO (senha pedida na hora, usada para o bind e
  descartada). Nao existe conta de servico de escrita nem senha gravada no servidor.
- A permissao vem da delegacao no AD: Painel_Admin_TI pode escrever a propriedade `member` dos
  grupos Impressora_*. O painel nao precisa (nem tem) poder alem disso.
- Padrao: cada pessoa fica em UM so grupo de nivel por impressora. Definir um nivel = entrar no
  grupo desse nivel e sair dos demais. "Sem acesso" = sair de todos. Sempre ENTRA primeiro e
  SO DEPOIS sai, para que uma falha no meio nunca deixe a pessoa sem acesso.
- A lista de alteracoes fica no SQLite do painel, por usuario logado, e some no login/logout.
"""
import json
import re
import secrets
import time

from ldap3 import MODIFY_ADD, MODIFY_DELETE
from ldap3.core.exceptions import LDAPException
from ldap3.utils.conv import escape_filter_chars

import ad_leitura as AD
import auth
import impressoras as REG

LOGIN_OK = re.compile(r"^[A-Za-z0-9._-]{1,40}$")
BASE_GRUPOS = "DC=empresa,DC=local"
MAX_LISTA = 100
NENHUM = "nenhum"
PC_PREFIXO = "pc:"                 # itens de computador: login = "pc:NOME" (nunca colide com login de usuario)
PC_ADD, PC_DEL = "pc_add", "pc_del"
PC_ACOES = (PC_ADD, PC_DEL)
PC_OK = re.compile(r"^[A-Za-z0-9._-]{1,63}$")
# codigos LDAP que significam "ja estava assim"
JA_ADD = {20, 68}      # attributeOrValueExists / entryAlreadyExists
JA_DEL = {16}          # noSuchAttribute


class ErroEscrita(Exception):
    """Falha que impede a alteracao (grupo ou usuario nao encontrado, rede)."""


# ---------- alvos (impressora + nivel) ----------

def alvos(imps=None):
    """Mapa 'id_impressora:id_nivel' -> (impressora, nivel ou None para 'sem acesso')."""
    saida = {}
    for p in (imps if imps is not None else REG.IMPRESSORAS):
        for n in p["niveis"]:
            saida[f"{p['id']}:{n['id']}"] = (p, n)
        saida[f"{p['id']}:{NENHUM}"] = (p, None)
    return saida


def rotulo(p, n):
    return f"{p['nome']} · {n['rotulo'] if n else 'Sem acesso'}"


def nivel_atual(p, acesso):
    """Rotulo do nivel atual de um usuario (dict acesso do ad_leitura) na impressora p."""
    nid = (acesso or {}).get(p["id"])
    for n in p["niveis"]:
        if n["id"] == nid:
            return n["rotulo"]
    return "Sem acesso"


# ---------- lista (SQLite do painel) ----------

def adicionar(ator, logins, alvo, dados):
    """Poe pessoas na lista. Devolve (quantas_entraram, [(login, motivo)])."""
    mapa = alvos()
    if alvo not in mapa:
        return 0, [("-", "alvo invalido")]
    p, n = mapa[alvo]
    por_login = {u["login"].lower(): u for u in dados["usuarios"] if not u.get("fora")}
    entrou, rejeitados = 0, []
    con = auth._db()
    try:
        ja = con.execute("SELECT COUNT(*) FROM lista_alteracoes WHERE ator=?", (ator,)).fetchone()[0]
        for login in dict.fromkeys(logins):          # sem repetidos, mantem a ordem
            u = por_login.get(login.lower()) if LOGIN_OK.match(login or "") else None
            if u is None:
                rejeitados.append((login[:40], "usuário não encontrado"))
                continue
            if n is not None and not u["ativo"]:
                rejeitados.append((u["login"], "conta desativada"))
                continue
            existe = con.execute("SELECT 1 FROM lista_alteracoes WHERE ator=? AND impressora=? "
                                 "AND login=?", (ator, p["id"], u["login"])).fetchone()
            if not existe and ja >= MAX_LISTA:
                rejeitados.append((u["login"], f"lista cheia (máximo {MAX_LISTA})"))
                continue
            con.execute("INSERT OR REPLACE INTO lista_alteracoes (ator, impressora, login, nivel, criado) "
                        "VALUES (?,?,?,?,?)", (ator, p["id"], u["login"],
                                              n["id"] if n else NENHUM, time.time()))
            if not existe:
                ja += 1
            entrou += 1
        con.commit()
    finally:
        con.close()
    return entrou, rejeitados


def adicionar_pcs(ator, nomes, imp_id, acao, dados):
    """Poe computadores na lista (incluir no / tirar do filtro _PCs). Devolve (entraram, [(nome, motivo)])."""
    p = next((x for x in REG.IMPRESSORAS if x["id"] == imp_id), None)
    if p is None or acao not in PC_ACOES:
        return 0, [("-", "alvo invalido")]
    por_nome = {m["nome"].lower(): m for m in dados["pcs"] if not m.get("fora")}
    entrou, rejeitados = 0, []
    con = auth._db()
    try:
        ja = con.execute("SELECT COUNT(*) FROM lista_alteracoes WHERE ator=?", (ator,)).fetchone()[0]
        for nome in dict.fromkeys(nomes):
            m = por_nome.get(nome.lower()) if PC_OK.match(nome or "") else None
            if m is None:
                rejeitados.append((nome[:40], "computador não encontrado"))
                continue
            if acao == PC_ADD and not m["ativo"]:
                rejeitados.append((m["nome"], "computador desativado"))
                continue
            chave = PC_PREFIXO + m["nome"]
            existe = con.execute("SELECT 1 FROM lista_alteracoes WHERE ator=? AND impressora=? "
                                 "AND login=?", (ator, p["id"], chave)).fetchone()
            if not existe and ja >= MAX_LISTA:
                rejeitados.append((m["nome"], f"lista cheia (máximo {MAX_LISTA})"))
                continue
            con.execute("INSERT OR REPLACE INTO lista_alteracoes (ator, impressora, login, nivel, criado) "
                        "VALUES (?,?,?,?,?)", (ator, p["id"], chave, acao, time.time()))
            if not existe:
                ja += 1
            entrou += 1
        con.commit()
    finally:
        con.close()
    return entrou, rejeitados


def listar(ator):
    con = auth._db()
    try:
        return [{"id": r[0], "impressora": r[1], "login": r[2], "nivel": r[3]} for r in con.execute(
            "SELECT id, impressora, login, nivel FROM lista_alteracoes WHERE ator=? ORDER BY id",
            (ator,))]
    finally:
        con.close()


def remover(ator, item_id):
    con = auth._db()
    try:
        con.execute("DELETE FROM lista_alteracoes WHERE ator=? AND id=?", (ator, item_id))
        con.commit()
    finally:
        con.close()


def limpar(ator):
    con = auth._db()
    try:
        con.execute("DELETE FROM lista_alteracoes WHERE ator=?", (ator,))
        con.commit()
    finally:
        con.close()


def guardar_lote(ator, lote):
    con = auth._db()
    try:
        con.execute("INSERT OR REPLACE INTO ultimo_lote VALUES (?,?,?)",
                    (ator, json.dumps(lote, ensure_ascii=False), time.time()))
        con.commit()
    finally:
        con.close()


def ler_lote(ator):
    con = auth._db()
    try:
        lin = con.execute("SELECT json FROM ultimo_lote WHERE ator=?", (ator,)).fetchone()
    finally:
        con.close()
    return json.loads(lin[0]) if lin else None


def fechar_lote(ator):
    con = auth._db()
    try:
        con.execute("DELETE FROM ultimo_lote WHERE ator=?", (ator,))
        con.commit()
    finally:
        con.close()


# ---------- leitura pela conexao do usuario ----------

def _um_dn_usuario(con, login):
    filtro = ("(&(objectClass=user)(!(objectClass=computer))"
              f"(sAMAccountName={escape_filter_chars(login)}))")
    for r in con.extend.standard.paged_search(AD.BASE_USUARIOS, filtro,
                                              attributes=["sAMAccountName"],
                                              paged_size=5, generator=True):
        if r.get("type") == "searchResEntry":
            return r["dn"]
    return None


def _um_dn_computador(con, nome):
    filtro = f"(&(objectClass=computer)(sAMAccountName={escape_filter_chars(nome + '$')}))"
    for r in con.extend.standard.paged_search(AD.BASE_RAIZ, filtro, attributes=["sAMAccountName"],
                                              paged_size=5, generator=True):
        if r.get("type") == "searchResEntry":
            return r["dn"]
    return None


_RANGE = re.compile(r"^member;range=(\d+)-(\d+|\*)$", re.I)


def _ler_grupo(con, nome):
    """Devolve (dn, conjunto de DNs membros em minusculas) ou levanta ErroEscrita.

    O AD entrega `member` em blocos (range retrieval, ~1500 por vez): le todos os blocos.
    """
    filtro = f"(&(objectClass=group)(cn={escape_filter_chars(nome)}))"
    for r in con.extend.standard.paged_search(BASE_GRUPOS, filtro, attributes=["member"],
                                              paged_size=5, generator=True):
        if r.get("type") != "searchResEntry":
            continue
        dn = r["dn"]
        membros = set()
        attrs = r["attributes"]
        for _ in range(1000):                      # trava de seguranca contra laco infinito
            fim = True
            for chave, valor in attrs.items():
                if chave.lower() == "member":
                    membros.update(m.lower() for m in AD._lista(valor))
                    continue
                mt = _RANGE.match(chave)
                if mt:
                    membros.update(m.lower() for m in AD._lista(valor))
                    if mt.group(2) != "*":
                        proximo = int(mt.group(2)) + 1
                        attrs = _bloco(con, dn, proximo)
                        fim = False
                        break
            if fim:
                break
        return dn, membros
    raise ErroEscrita(f"grupo {nome} não encontrado no AD")


def _bloco(con, dn, inicio):
    for r in con.extend.standard.paged_search(dn, "(objectClass=group)", attributes=[f"member;range={inicio}-*"],
                                              paged_size=5, generator=True):
        if r.get("type") == "searchResEntry":
            return r["attributes"]
    raise ErroEscrita("falha ao ler os membros do grupo")


# ---------- aplicar ----------

def _modificar(con, gdn, udn, operacao):
    """Executa uma troca de pertenca. Devolve ('ok'|'ja'|'erro', descricao)."""
    mod = MODIFY_ADD if operacao == "add" else MODIFY_DELETE
    try:
        ok = con.modify(gdn, {"member": [(mod, [udn])]})
        res = getattr(con, "result", None) or {}
    except (LDAPException, OSError) as e:
        return "erro", type(e).__name__
    if ok:
        return "ok", "ok"
    codigo = res.get("result")
    if (operacao == "add" and codigo in JA_ADD) or (operacao == "del" and codigo in JA_DEL):
        return "ja", "já estava assim"
    return "erro", str(res.get("description") or f"código {codigo}")


def _aplicar_com(con, ator, origem, itens, lote_id):
    imps = {p["id"]: p for p in REG.IMPRESSORAS}
    grupos, dns_alvo = {}, {}
    saida = []

    def grupo(nome):
        chave = nome.lower()
        if chave not in grupos:
            grupos[chave] = _ler_grupo(con, nome)
        return grupos[chave]

    def passo(reg, op, gnome, alvo_login, udn):
        """Executa uma troca de pertenca e registra. Devolve o estado ('ok'|'ja'|'erro')."""
        gdn, membros = grupo(gnome)
        estado, desc = _modificar(con, gdn, udn, op)
        reg["passos"].append({"op": op, "grupo": gnome, "res": estado, "desc": desc})
        auth.auditar("grupo_alterado", ator, origem,
                     f"lote={lote_id} op={op} grupo={gnome} alvo={alvo_login} resultado={estado}"
                     + ("" if estado != "erro" else f" ({desc})"))
        if estado == "erro":
            reg["status"] = "erro"
            reg["msg"] = f"{desc}"
        elif estado == "ok":
            if op == "add":
                membros.add(udn.lower())
            else:
                membros.discard(udn.lower())
        return estado

    for it in itens:
        p = imps.get(it["impressora"])
        reg = {"item": it["id"], "login": it["login"], "impressora": it["impressora"],
               "nivel": it["nivel"], "passos": [], "status": "ok", "msg": ""}
        saida.append(reg)
        try:
            if p is None:
                raise ErroEscrita("impressora não está mais no cadastro")
            if it["nivel"] in PC_ACOES:                       # --- computador no filtro (_PCs)
                nome_pc = it["login"][len(PC_PREFIXO):]
                add = it["nivel"] == PC_ADD
                reg["rotulo"] = ("Liberar " if add else "Retirar ") + p["nome"]
                chave = "pc:" + nome_pc.lower()
                if chave not in dns_alvo:
                    dns_alvo[chave] = _um_dn_computador(con, nome_pc)
                cdn = dns_alvo[chave]
                if not cdn:
                    raise ErroEscrita("computador não encontrado nas OUs do AD")
                gdn, membros = grupo(p["grupo_pcs"])
                if (cdn.lower() in membros) == add:           # ja esta como se quer
                    reg["status"], reg["msg"] = "igual", "já estava assim"
                    continue
                estado = passo(reg, "add" if add else "del", p["grupo_pcs"], it["login"], cdn)
                if estado == "ja":
                    reg["status"], reg["msg"] = "igual", "já estava assim"
                continue
            niveis = {n["id"]: n for n in p["niveis"]}
            if it["nivel"] != NENHUM and it["nivel"] not in niveis:
                raise ErroEscrita("nível não existe mais no cadastro")
            alvo = niveis.get(it["nivel"])
            reg["rotulo"] = rotulo(p, alvo)
            if it["login"] not in dns_alvo:
                dns_alvo[it["login"]] = _um_dn_usuario(con, it["login"])
            udn = dns_alvo[it["login"]]
            if not udn:
                raise ErroEscrita("usuário não encontrado na OU de usuários")
            plano = []
            if alvo is not None:
                gdn, membros = grupo(alvo["grupo"])
                if udn.lower() not in membros:
                    plano.append(("add", alvo["grupo"]))
            for n in p["niveis"]:
                if alvo is not None and n["id"] == alvo["id"]:
                    continue
                gdn, membros = grupo(n["grupo"])
                if udn.lower() in membros:
                    plano.append(("del", n["grupo"]))
            if not plano:
                reg["status"] = "igual"
                reg["msg"] = "já estava assim"
                continue
            # entra primeiro, sai depois
            plano.sort(key=lambda x: 0 if x[0] == "add" else 1)
            for op, gnome in plano:
                if passo(reg, op, gnome, it["login"], udn) == "erro":
                    break                      # nunca tira o acesso antigo se a entrada falhou
            if reg["status"] == "ok" and all(s["res"] == "ja" for s in reg["passos"]):
                reg["status"] = "igual"
                reg["msg"] = "já estava assim"
        except ErroEscrita as e:
            reg["status"], reg["msg"] = "erro", str(e)
            auth.auditar("grupo_erro", ator, origem, f"lote={lote_id} alvo={it['login']}: {e}")
        except (LDAPException, OSError) as e:
            reg["status"], reg["msg"] = "erro", "falha de comunicação com o domínio"
            auth.auditar("grupo_erro", ator, origem,
                         f"lote={lote_id} alvo={it['login']}: {type(e).__name__}")
    return saida


def aplicar(ator, senha, origem):
    """Aplica a lista com a senha de quem esta logado.

    Devolve (lote, None) ou (None, codigo) com codigo em: vazia, senha, bloqueado, ldap.
    """
    itens = listar(ator)
    if not itens:
        return None, "vazia"
    con, codigo = auth.conexao_usuario(ator, senha, origem)
    if con is None:
        auth.auditar("alteracao_recusada", ator, origem, "reautenticacao: " + codigo)
        return None, codigo
    lote_id = secrets.token_hex(4)
    try:
        resultados = _aplicar_com(con, ator, origem, itens, lote_id)
    finally:
        try:
            con.unbind()
        except Exception:
            pass
    # o que deu certo (ou ja estava assim) sai da lista; o que falhou fica para tentar de novo
    for r in resultados:
        if r["status"] in ("ok", "igual"):
            remover(ator, r["item"])
    n = {s: sum(1 for r in resultados if r["status"] == s) for s in ("ok", "igual", "erro")}
    lote = {"id": lote_id, "quando": time.strftime("%d/%m/%Y %H:%M:%S"), "ator": ator,
            "itens": resultados, "n_ok": n["ok"], "n_igual": n["igual"], "n_erro": n["erro"]}
    auth.auditar("lote_aplicado", ator, origem,
                 f"lote={lote_id} ok={n['ok']} igual={n['igual']} erro={n['erro']}")
    guardar_lote(ator, lote)
    return lote, None
