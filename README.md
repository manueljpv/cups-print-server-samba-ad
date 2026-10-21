# cups-print-server-samba-ad

**Português** · [English](README.en.md) · [Español (Honduras)](README.es-HN.md)

Servidor de impressão **CUPS em Linux** integrado a um domínio **Samba AD**, para quem aluga impressoras cobradas por página impressa e precisa saber quem imprimiu o quê, em P&B ou colorido, sem pagar licenças de Windows Print Server. Ele preserva a **impressão protegida por PIN** da Xerox, conta as páginas por usuário, restringe a cor por grupo do AD e entrega as impressoras aos PCs por GPO.

> **Aviso: dados fictícios.** Todos os nomes, domínios, IPs e hostnames deste repositório (`empresa.local`, `srv-cups`, `192.0.2.x`, `usuario.a`…) são exemplos inventados. Nada aqui vem de um ambiente real. Veja a [seção final](#aviso-dados-fictícios).

## O problema

- O contrato de locação das impressoras cobra **por face impressa**, com valores diferentes para P&B e colorido. Sem contabilidade própria, a fatura é uma caixa-preta.
- Não havia orçamento para licenciar um Windows Server e CALs só para ter servidor de impressão.
- A impressão protegida por **PIN** da Xerox (usada, por exemplo, pelo RH) precisava continuar funcionando.
- O CUPS padrão não resolve isso sozinho: a fila IPP conta páginas mas **perde o PIN**; a fila raw **mantém o PIN** mas só conta 1 por job; e os drivers do Windows não enviam a cor como atributo IPP.
- Distribuir impressoras a cada PC, mostrando só as que o usuário pode usar, é trabalho manual e propenso a erro.

## O que o projeto entrega

**1. Filtro de contagem do CUPS (`scripts/server/xerox-contagem`)**

- Entrega o arquivo do job **intacto** à impressora (o PIN é preservado) e grava a contabilidade lendo o cabeçalho do próprio arquivo: usuário, fila, páginas, cópias, frente e verso e cor.
- **Controle de cor por grupo do AD:** quem pede colorido sem estar no grupo autorizado recebe P&B, sem perder o trabalho.
- **PIN obrigatório:** job sem PIN é rejeitado em silêncio e registrado.
- Um arquivo de log por mês, com campos separados por TAB, pronto para alimentar relatórios.

**2. Receptor de porta TCP (`scripts/server/cups-recebe` + `configs/systemd/`)**

- Recebe o job do Windows numa porta TCP RAW (uma por fila, por exemplo 9101) e o entrega ao CUPS, passando pelo filtro.
- Controlado pelo systemd, com restrição de origem por sub-rede.

**3. Entrega automática por GPO (`scripts/windows/Sync-Impressoras.ps1`)**

- Tarefa agendada que roda no logon como `SYSTEM`: lê os grupos do usuário no AD, instala o driver V4 PS, cria a porta e a fila com nome amigável, aplica **P&B como padrão** e liga o **PIN**.
- Remove as impressoras que o usuário não pode usar e, opcionalmente, limpa as demais (Canon, XPS, Fax etc.).
- Uma impressora nova é uma linha em `impressoras.json`.

**4. Troca controlada da senha da conta de máquina (`scripts/server/troca-senha-maquina` + `configs/systemd/`)**

- Desliga a troca automática do Samba e a substitui por uma troca agendada que **reinicia o winbind**, testa se os grupos continuam visíveis e grava um status em JSON.
- Resolve o incidente em que todos os usuários passaram a sair em P&B. Veja o [doc 06](docs/06-troca-controlada-winbind.md).

**5. Painel web (`painel/`)**

- Aplicação Flask interna, com login do AD (LDAPS) e acesso por grupo. Hoje traz **permissões de impressão** (quem pode usar cada impressora, por usuário, departamento, impressora e computador; somente leitura) e **controle do winbind** (saúde, última troca e botão de troca). Veja o [doc 07](docs/07-painel-web.md).

**6. Documentação e lições aprendidas (`docs/`)**

- Decisões e testes que descartaram as alternativas, problemas comuns e um estudo de caso de incidente (winbind sem grupos após a troca da senha da conta de máquina).

## Arquitetura em alto nível

```
Impressão:
PC Windows ──► driver Xerox V4 PS ──► porta TCP 9101 ──► cups-recebe (systemd) ──► lp
                                                                                    │
                                                                                    ▼
                                                              CUPS (fila adm-xerox) + filtro xerox-contagem
                                                               │  consulta grupos (winbind: id -nG)
                                                               │  grava /var/log/cups-contabilidade/contagem-AAAA-MM.log
                                                               ▼
                                                  Impressora Xerox (IPP) ──► PIN liberado no painel

Entrega das impressoras:
PC Windows ──► GPO (tarefa agendada no logon, SYSTEM) ──► Sync-Impressoras.ps1
                                                           ├─ grupos do usuário (AD, via ADSI)
                                                           ├─ impressoras.json (NETLOGON)
                                                           └─ instala ou remove fila, porta e driver
```

O arquivo do job passa pelo CUPS sem ser convertido, porque o driver Xerox embute PIN, cor e lados num cabeçalho XML (XPIF) dentro do próprio arquivo. O filtro lê esse cabeçalho. Por que essa é a única opção que mantém PIN e contagem juntos está em [`docs/01-visao-geral-e-decisoes.md`](docs/01-visao-geral-e-decisoes.md).

## Pré-requisitos

**Servidor de impressão**

- VM com **Ubuntu Server 24.04 LTS** (CUPS 2.4), com 2 vCPU, 4 GB de RAM e 32 GB de disco como ponto de partida.
- Servidor **ingressado no domínio Samba AD** (winbind/Kerberos), de forma que `wbinfo -t` funcione e `id usuario` mostre os grupos do AD. O passo a passo do ingresso não está neste repositório.
- Python 3 (já vem no Ubuntu).

**Impressora**

- Uma Xerox com PIN de impressão protegida (o projeto usou a **AltaLink C8030**), acessível por IPP.
- Outras marcas exigem testar o que o driver grava no arquivo do job antes de reaproveitar o filtro.

**Domínio e clientes**

- Samba AD (ou Active Directory) com GPO e uma pasta compartilhada legível pelos computadores (os exemplos usam o `NETLOGON`).
- PCs com Windows 10/11 ingressados no domínio.
- O pacote do driver **Xerox AltaLink C8030 V4 PS** (baixe do site oficial da Xerox; este repositório **não** inclui o driver).
- Uma máquina com RSAT para criar a GPO e escrever no `NETLOGON` como administrador do domínio.

## Implantação

### 1. Servidor (Linux)

1. **Desative o `cups-browsed`**, que cria filas automáticas ao abrir o CUPS para a rede:

   ```bash
   systemctl disable --now cups-browsed && systemctl mask cups-browsed
   ```

2. **Libere o CUPS para a rede e defina o `PageLogFormat`**, usando [`configs/cupsd-location.conf`](configs/cupsd-location.conf) como modelo (um `Allow` por sub-rede de usuários). Depois: `systemctl restart cups`.
3. **Instale o filtro e a pasta de contabilidade:**

   ```bash
   install -o root -g root -m 755 scripts/server/xerox-contagem /usr/lib/cups/filter/xerox-contagem
   mkdir -p /var/log/cups-contabilidade
   chown lp:lp /var/log/cups-contabilidade && chmod 750 /var/log/cups-contabilidade
   ```

   No topo do filtro, ajuste `GRUPOS_COR` (fila → grupo de cor) e `FILAS_PIN` (filas em que o PIN é obrigatório).
4. **Crie a fila** com o PPD mínimo [`configs/xerox-contagem.ppd`](configs/xerox-contagem.ppd), que tem as duas linhas `*cupsFilter` descritas em [`docs/02-filtro-de-contagem.md`](docs/02-filtro-de-contagem.md):

   ```bash
   lpadmin -p adm-xerox -E -v ipp://192.0.2.20/ipp/print \
           -P configs/xerox-contagem.ppd \
           -L "Prédio Administrativo" -D "Xerox AltaLink C8030 - ADM" \
           -o printer-is-shared=true
   ```

5. **Crie os grupos no AD**, no controlador de domínio (um de acesso e um de cor):

   ```bash
   /usr/local/samba/bin/samba-tool group add Impressora_Xerox_ADM \
       --groupou="OU=grupos,OU=EMPRESA" --group-scope=Global --group-type=Security
   /usr/local/samba/bin/samba-tool group add Impressora_Xerox_ADM_Cor \
       --groupou="OU=grupos,OU=EMPRESA" --group-scope=Global --group-type=Security
   ```

6. **Instale o receptor da porta TCP:**

   ```bash
   install -m 755 scripts/server/cups-recebe /usr/local/bin/cups-recebe
   cp configs/systemd/cups-recebe-adm-xerox.socket configs/systemd/cups-recebe-adm-xerox@.service /etc/systemd/system/
   mkdir -p /etc/systemd/system/cups-recebe-adm-xerox.socket.d
   cp configs/systemd/ip.conf.example /etc/systemd/system/cups-recebe-adm-xerox.socket.d/ip.conf   # ajuste as sub-redes
   systemctl daemon-reload && systemctl enable --now cups-recebe-adm-xerox.socket
   ```

### 2. Clientes Windows (GPO)

1. Coloque o pacote do driver V4 PS (descompactado) numa pasta legível por **Domain Computers** (os exemplos usam `\\empresa.local\NETLOGON\Impressoras\XeroxV4PS`).
2. Copie `scripts/windows/Sync-Impressoras.ps1` e o seu `impressoras.json` (a partir de [`configs/impressoras.json.example`](configs/impressoras.json.example)) para `\\empresa.local\NETLOGON\scripts\Impressoras\CUPS\`. Escreva ali como administrador do domínio.
3. Crie um grupo de computadores para o piloto e uma GPO filtrada por ele, com uma **tarefa agendada de computador** (conta `SYSTEM`, disparo "ao fazer logon, qualquer usuário, atraso de 30 segundos") que execute o script. Todos os parâmetros estão em [`docs/03-entrega-por-gpo.md`](docs/03-entrega-por-gpo.md).
4. Adicione os usuários aos grupos de acesso (e, se for o caso, de cor) e peça um logoff/logon.

## Como validar

**Servidor**

- `id usuario.a` deve listar os grupos de impressora do AD.
- Teste sem papel: `cupsdisable adm-xerox`, depois `nc -w 5 127.0.0.1 9101 < amostra.ps`, e confira `journalctl -u 'cups-recebe-adm-xerox@*'` e `lpstat -o adm-xerox`. Para voltar ao normal: `cancel -a adm-xerox` e `cupsenable adm-xerox`.
- `tail -n 5 /var/log/cups-contabilidade/contagem-$(date +%Y-%m).log` mostra usuário, páginas, cópias, cor efetiva, cor pedida, nota e PIN de cada job.

**Cliente**

- O arquivo `C:\ProgramData\Impressoras-CUPS\sync.log` mostra os grupos do usuário e o que foi instalado ou removido.
- `Get-Printer` deve listar só a impressora permitida e a "Microsoft Print to PDF" (se a limpeza estiver ativa).
- Imprima com PIN: o job fica retido no painel da Xerox (Trabalhos > Impressão protegida). Sem PIN, o job é rejeitado (`rejeitado-sem-pin` no log). Um usuário fora do grupo de cor pedindo colorido sai em P&B (`forcado-pb`).

## Problemas comuns

| Sintoma | Causa provável | O que fazer |
| --- | --- | --- |
| HTTP 403 ao acessar o CUPS | O `<Location />` só permite uma sub-rede | Acrescente um `Allow` por sub-rede de usuários e reinicie o CUPS |
| O job sai com dezenas de páginas de "códigos" e sem PIN | O CUPS classificou o arquivo como `text/plain` e descartou o cabeçalho | Acrescente `*cupsFilter: "text/plain 0 xerox-contagem"` ao PPD (veja o doc 04) |
| "Não chegou nada na impressora" | O job está retido aguardando o PIN | Confira o painel da Xerox antes de culpar o driver |
| Todos os usuários saem em P&B | O winbind parou de enxergar os grupos (troca da senha da conta de máquina) | `systemctl restart winbind`; veja o [estudo de caso](docs/05-incidente-winbind-senha-de-maquina.md) e a [troca controlada](docs/06-troca-controlada-winbind.md), que evita o problema |
| A contabilidade parou de gravar, sem erro | Pasta ou log com dono errado (teste feito como root) | `chown lp:lp` na pasta e nos arquivos |
| As preferências do driver voltaram a colorido e sem PIN | `Rename-Printer` zera os padrões | Crie a fila já com o nome final e só depois aplique os padrões |
| O PowerShell "como administrador" não vê o domínio nem o `NETLOGON` | O administrador local é uma conta local | Teste com uma tarefa agendada como `SYSTEM` ou com o PowerShell do usuário de domínio |
| Não consegue remover fila e driver logo em seguida | O spooler segura os itens | Espere, ou `Restart-Service Spooler` e aguarde ~20 s |

Mais casos em [`docs/04-problemas-comuns.md`](docs/04-problemas-comuns.md).

## Limitações conhecidas

- A contagem é feita **no envio**: um job cancelado depois (no painel da impressora, ou antes de liberar o PIN) continua contado.
- Cor e cópias refletem o que o driver pediu, não uma análise página a página.
- O nome do usuário vem do Windows e **não é validado** pelo servidor.
- Filas raw e drivers PPD são marcados como obsoletos pelo CUPS. No CUPS 2.4 (Ubuntu 24.04) isso não afeta hoje, mas é um risco de longo prazo.
- O filtro foi validado com Xerox (cabeçalho XPIF). Outras marcas precisam de testes.

## Segurança

- A **porta TCP do receptor não tem autenticação** e o `cupsd.conf` não vale para ela. Restrinja a origem por sub-rede (`IPAddressAllow` no socket, como no exemplo) e/ou por firewall.
- O PIN dentro do arquivo do job é só uma **codificação simples**, não criptografia. Mantenha `PreserveJobFiles` desligado em produção e a pasta de spool protegida.
- Faça **backup do SYSVOL (com permissões)** antes de atualizar o Samba, principalmente se ele foi instalado por tarball.
- Escreva no `NETLOGON` apenas como administrador do domínio; os computadores só precisam de leitura.
- A senha da conta de máquina do servidor é trocada automaticamente a cada 7 dias (padrão do Samba) e isso pode quebrar a leitura de grupos: o winbind em execução continua com a senha antiga. Desligue a troca automática e use a [troca controlada](docs/06-troca-controlada-winbind.md).
- O painel web deve ficar atrás de um proxy que aceite só as redes internas e **nunca** ser exposto à internet. Não versione a senha da conta de leitura nem a chave de sessão.
- Nunca versione `impressoras.json` reais, logs de contabilidade, chaves ou certificados (o `.gitignore` já bloqueia esses arquivos).

## Documentação e roadmap

- [`docs/01-visao-geral-e-decisoes.md`](docs/01-visao-geral-e-decisoes.md): objetivo, ambiente, decisões e os testes que descartaram as alternativas.
- [`docs/02-filtro-de-contagem.md`](docs/02-filtro-de-contagem.md): como o filtro funciona, versões e formato do log.
- [`docs/03-entrega-por-gpo.md`](docs/03-entrega-por-gpo.md): porta TCP, grupos, GPO e o script de sincronização.
- [`docs/04-problemas-comuns.md`](docs/04-problemas-comuns.md): problemas e soluções.
- [`docs/05-incidente-winbind-senha-de-maquina.md`](docs/05-incidente-winbind-senha-de-maquina.md): estudo de caso.
- [`docs/06-troca-controlada-winbind.md`](docs/06-troca-controlada-winbind.md): causa confirmada e solução da troca da senha da conta de máquina.
- [`docs/07-painel-web.md`](docs/07-painel-web.md): painel web (permissões, winbind, instalação).
- [`ROADMAP.md`](ROADMAP.md): melhorias futuras.

A pasta `docs/` está disponível apenas em português.

## Aviso: dados fictícios

Este repositório foi derivado de um projeto real de infraestrutura e **passou por anonimização antes da publicação**. Todos os nomes de empresa, domínios, endereços IP, hostnames, contas e pessoas que aparecem aqui são **fictícios** e servem apenas de exemplo:

- Domínio: `empresa.local` (NetBIOS `EMPRESA`).
- Redes: `192.0.2.0/24`, `198.51.100.0/24` e `203.0.113.0/24` (faixas reservadas para documentação).
- Máquinas e contas: `dc01`, `srv-cups`, `srv-arquivos`, `usuario.a`, `usuario.b` etc.

Os valores de `impressoras.json.example` e dos arquivos em `configs/` são apenas marcadores. Substitua tudo pelo seu ambiente.

## Licença

[GNU GPL v3.0](LICENSE).

Mantido por [@manueljpv](https://github.com/manueljpv).
