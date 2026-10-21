# Painel web: permissões, controle do winbind e avisos

> Dados fictícios. Código em [`painel/`](../painel).

## O que é

Uma aplicação web interna (Python + Flask) para simplificar a operação do servidor de impressão. O objetivo é **simplificar**: mostrar exatamente quem pode imprimir em cada impressora, deixar a TI ver a saúde do winbind e, mais adiante, alterar permissões sem depender de lembrar o grupo certo do AD.

Ela é pensada para **notebook e desktop** da rede interna, não para celular, e fica **atrás de um proxy reverso (HTTPS) que só aceita as redes internas**. Não publique o painel na internet.

## As três páginas

| Página | Para quem | O que faz | Estado |
| --- | --- | --- | --- |
| **Controle de impressões** (`/impressoes`) | Gestores e TI | Relatórios, custo e rateio, a partir do log de contagem | Esqueleto; a versão enxuta ainda será feita |
| **Permissões de impressão** (`/permissoes`) | Só TI | Quem tem acesso a cada impressora, por usuário, departamento, impressora e computador | **Etapa 1 (somente leitura) pronta** |
| **Winbind** (`/winbind`) | Só TI | Saúde do winbind, data da última troca da senha da máquina e botão para trocar | **Pronta** |

Mais uma rota sem login, **somente leitura e restrita ao IP de uma tela de parede**: `/carrossel/winbind`, uma página de status que muda de cor conforme a proximidade da troca da senha ou uma falha. Ela foi pensada para o [`tv-kiosk-carousel`](https://github.com/manueljpv/tv-kiosk-carousel).

## Acesso e segurança

- **Um login só**, com usuário e senha do AD. O painel faz o *bind* LDAPS com a **própria senha do usuário**, direto no DC, e lê os grupos dele. Não há conta de serviço no login nem senha guardada, e ele não depende do winbind do servidor de impressão.
- **Acesso por grupo do AD:** o grupo da TI (`Painel_Admin_TI`) acessa as páginas de permissões e winbind; os gestores (por exemplo, `Relatorio_Impressao`) acessam só a de controle de impressões. Quem não tem o grupo recebe 403.
- **Sessão:** expira com 10 minutos sem atividade, tem teto absoluto de 8 horas e é por aba (fechar a janela exige novo login). O cookie guarda só um token aleatório; o banco guarda apenas o **HMAC** dele.
- **Bloqueio:** 5 minutos depois de 5 erros seguidos, por usuário e por origem.
- **Auditoria:** cada acesso e ação vai para um arquivo com um JSON por linha (`login_ok`, `login_falhou`, `login_bloqueado`, `acesso_negado`, `troca_solicitada`, `erro_leitura_ad` e outros), **sem senhas**.
- **Ações sensíveis exigem confirmação extra:** para trocar a senha da máquina, o usuário digita a própria senha de novo e a palavra `TROCAR`.
- **O servidor web não roda com poder total.** Ele roda como um usuário de sistema sem login (`painel`). A troca da senha da máquina passa por uma regra do polkit que permite iniciar **somente** uma unit (veja o [doc 06](06-troca-controlada-winbind.md)).
- **Conta de leitura:** a página de permissões usa uma conta separada (`svc-painel-leitura`), comum do domínio e **sem escrita**, por LDAPS com a CA do DC validada (`CERT_REQUIRED`). A senha dela fica num arquivo fora do código, legível só pelo root e pelo usuário do painel. **Nunca cole essa senha em chat, e-mail ou repositório.**

## Estrutura do código

| Arquivo | Função |
| --- | --- |
| `app_novo.py` | Aplicação Flask: base HTML, login, sair, `/saude` e registro das páginas |
| `auth.py` | Login por LDAPS, sessões, bloqueio de tentativas, papéis e reautenticação |
| `visual.py` | Estilo (CSS) e ícones; tema claro/escuro automáticos, sem fontes externas |
| `pag_winbind.py` | Página do winbind (lê o `status.json` do [doc 06](06-troca-controlada-winbind.md)) |
| `pag_carrossel.py` | Página de status para a tela de parede (sem login, só um IP) |
| `pag_permissoes.py` | Página de permissões (quatro visões, busca, ordenação) |
| `ad_leitura.py` | Leitura do AD (usuários, computadores e membros dos grupos) |
| `impressoras.py` | Cadastro das impressoras (**valores fictícios**; troque pelos seus) |

As constantes que identificam o ambiente (`DC`, `DOMINIO`, `BASE_*`, `PROXY`, `IPS_PERMITIDOS`, os nomes dos grupos de papel) ficam **no topo de cada arquivo**; ajuste-as antes de usar. Dependências em [`painel/requirements.txt`](../painel/requirements.txt).

## Cadastro de impressoras

A página de permissões não é fixa em uma impressora: ela lê o `impressoras.py`. Cada item tem:

- `id`: identificador curto, sem espaços (vai na URL);
- `nome`, `modelo`, `ip`, `local`: texto mostrado na página;
- `niveis`: do **maior para o menor** acesso; cada um aponta para um grupo do AD (`rotulo`, `grupo` e `pilula`, que define a cor da etiqueta: `cor`, `info` ou `ok`). Impressora sem cor usa um nível só, "Imprimir";
- `grupo_pcs`: grupo do AD com os **computadores** liberados nessa impressora (o filtro da GPO).

Padrão de nomes dos grupos: `Impressora_<Marca>_<Local>`, `..._Cor` para o nível colorido e `..._PCs` para os computadores. Para incluir uma impressora: crie os grupos no AD, acrescente um bloco no arquivo e reinicie o serviço. Um grupo citado no cadastro e inexistente no AD aparece como aviso na página, sem quebrar nada.

## Página de permissões (etapa 1, somente leitura)

Quatro visões, que abrem em "Busca por usuário":

1. **Busca por usuário** (2 ou mais letras, sem acento, máximo de 50 resultados).
2. **Por departamento:** o departamento vem da **OU do usuário** (`users/<departamento>`), sem criar grupos por departamento. Mostra, por exemplo, "4 de 10 pessoas têm acesso", para questionar quem precisa mesmo.
3. **Por impressora:** quem está em cada nível.
4. **Computadores sem grupo:** computadores das OUs de departamento que ainda não estão no grupo `_PCs` da impressora.

Como ela lê o AD:

- Usuários de `OU=users`, computadores da raiz e a lista `member` dos grupos citados no cadastro, com cache de 60 s (há um link "Atualizar agora").
- Conta desativada não conta nos números e é sinalizada.
- **Pontos de atenção:** conta desativada ainda em grupo de impressora; membros fora das OUs de departamento (por exemplo `CN=Users`, `CN=Computers`, ou grupos aninhados); grupo do cadastro que não existe no AD.
- Servidores (OU `servidores`) não entram na conta de "computadores sem grupo".
- Quem entra na empresa aparece quando a conta é criada na OU do departamento. Quem sai deixa de contar quando a conta é desativada; uma conta ativa continua aparecendo como ativa (o painel não conhece o RH).
- Os cabeçalhos Nome, Login e Departamento ordenam as tabelas ao clicar, sem recarregar (script servido pelo próprio painel, sem JavaScript inline, por causa da política CSP).

## O que vem depois (etapa 2 e além)

- **Botões que alteram os grupos do AD,** com uma conta delegada que só pode mudar a pertença dos grupos `Impressora_*` (não administrador do domínio) e auditoria de quem, quando e o quê. O efeito não é imediato: depende do cache do winbind e do próximo logon.
- **Integração com o inventário (GLPI):** o AD não guarda qual computador é de qual usuário. Ao dar acesso a um usuário, o painel perguntaria "este usuário usa o computador X?", com a resposta vinda do campo "Usuário" do computador no GLPI, por uma API de somente leitura.
- **Revisão de acessos:** cruzar permissão com uso (quem tem cor e nunca imprimiu colorido, quem não imprime há 90 dias).
- **Página de controle de impressões** completa (relatórios, custos, franquia).
- **Página para adicionar e remover impressoras,** com cuidado especial com os **drivers**. É uma parte sensível e precisa de planejamento próprio.

## Limites do controle de acesso

- Só vale para o que **passa pelo servidor de impressão.** Quem imprime direto no IP da impressora (porta 9100) ignora as regras; para fechar isso, a impressora deveria aceitar só o servidor.
- O nome do usuário do job vem do Windows e **não é validado.**
- O bloqueio é silencioso; o painel lista as rejeições.

## Instalação

Exemplo para o mesmo servidor do CUPS (a opção mais simples para começar). Como uma atualização do CUPS não pode apagar o painel, ele fica isolado em `/opt/painel-impressao`, **pronto para migrar para uma VM dedicada.** Todos os comandos são como root; ajuste os valores fictícios.

**1. Usuário, pastas e dependências**

```bash
useradd --system --no-create-home --shell /usr/sbin/nologin painel
install -d -o painel -g painel -m 750 /opt/painel-impressao /var/lib/painel-impressao
install -d -o root -g painel -m 750 /etc/painel-impressao
apt install -y python3-venv
python3 -m venv /opt/painel-impressao/venv
/opt/painel-impressao/venv/bin/pip install -r painel/requirements.txt
install -o painel -g painel -m 664 painel/*.py /opt/painel-impressao/
```

**2. Grupos e conta de leitura no AD** (no controlador de domínio)

Crie os grupos `Painel_Admin_TI` (TI) e `Relatorio_Impressao` (gestores), com os membros certos, e uma conta comum do domínio `svc-painel-leitura`, **sem permissão de escrita**. Os nomes dos grupos de papel ficam no topo do `auth.py`.

**3. Segredos** (fora do código, em `/etc/painel-impressao`)

```bash
cp ca-do-dc.pem /etc/painel-impressao/ca-dc.pem        # a CA que assinou o certificado LDAPS do DC
openssl rand -hex 32 > /etc/painel-impressao/chave-sessao
install -m 640 -o root -g painel /dev/null /etc/painel-impressao/senha-leitura
read -rs SENHA && printf '%s' "$SENHA" > /etc/painel-impressao/senha-leitura; unset SENHA   # senha da conta de leitura
chown root:painel /etc/painel-impressao/*; chmod 640 /etc/painel-impressao/*
```

**4. Unidades do systemd e regra do polkit**

```bash
cp configs/systemd/painel-impressao.service configs/systemd/painel-impressao.socket /etc/systemd/system/
cp configs/polkit/50-painel-winbind.rules /etc/polkit-1/rules.d/
systemctl daemon-reload && systemctl enable --now painel-impressao.socket
```

O `painel-impressao.socket` escuta só no IP do servidor (`ListenStream`) e **nega tudo, exceto** o proxy, o próprio servidor e, se usar o alerta no carrossel, o IP da tela de parede (`IPAddressDeny=any` e `IPAddressAllow=`). O serviço roda sem privilégios extras (`NoNewPrivileges`, `ProtectSystem=strict`, `ProtectHome`, `PrivateTmp`) e só escreve em `/var/lib/painel-impressao`, onde ficam o banco SQLite das sessões e o arquivo de auditoria.

**5. Proxy reverso (HTTPS)**

Use o [`configs/caddy/Caddyfile.example`](../configs/caddy/Caddyfile.example) como modelo: certificado de uma CA interna, `remote_ip` só com as redes internas e `abort` para o resto. O painel usa o `X-Forwarded-For` somente quando a conexão vem do IP do proxy (constante `PROXY` em `app_novo.py` e `pag_winbind.py`). Para testar sem HTTPS, defina a variável de ambiente `PAINEL_COOKIE_SEGURO=0` (o cookie de sessão é `Secure` por padrão e não funciona em HTTP).

**6. Conferir**

```bash
curl -s http://192.0.2.10:8081/saude        # deve responder 200
journalctl -u painel-impressao -n 30 --no-pager
```

Entre pelo endereço do proxy com um usuário do grupo da TI e abra `/winbind` e `/permissoes`.

**Alerta no carrossel (opcional).** A rota `/carrossel/winbind` só responde ao IP em `IPS_PERMITIDOS` (`pag_carrossel.py`); para qualquer outro, dá 404. Como a tela de parede nem sempre resolve o nome interno nem confia no certificado interno, ela pode abrir a rota por HTTP direto no IP do servidor, na porta 8081 (por isso o IP dela está no `IPAddressAllow` do socket). O login do painel não funciona por esse caminho, de propósito.
