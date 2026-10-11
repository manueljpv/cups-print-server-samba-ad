# Entrega das impressoras aos usuários (porta TCP + GPO)

> Dados fictícios. Domínio `empresa.local`, DC `dc01`, servidor de impressão `srv-cups` (`192.0.2.10`).

## Por que porta TCP e não IPP ou Samba

Testes feitos em um PC Windows 11 do domínio, com PowerShell elevado:

- `Add-PrinterPort -Name "http://..."` falha (0x8007007b, nome inválido). Só o assistente gráfico cria a porta do tipo "Internet Port".
- `Add-Printer -ConnectionName "http://..."` falha (0x80070032), mesmo como administrador e com o driver já instalado.
- Em impressora ligada a uma Internet Port, `Set-PrintConfiguration -Color $false`, `Set-Printer -PortName` e a janela "Padrões de impressão" falham. Em porta TCP/IP comum, tudo funciona.
- Uma Internet Port criada pelo assistente pode ficar "presa" no PC (não sai por `Remove-PrinterPort` nem após reiniciar o spooler). Não atrapalha a porta TCP.
- **Compartilhar via Samba foi descartado:** não serve driver V4 de verdade, pode mandar o job como raw passando por cima do filtro, e um erro de acesso negado (0x80070005) apareceu nesse caminho SMB.

**Decisão:** o Windows envia para uma **porta TCP/IP RAW do servidor** (uma porta por fila, ex.: 9101 para `adm-xerox`). Um **receptor** no servidor entrega o job ao CUPS como PostScript, passando pelo filtro de contagem.

## Receptor no servidor

`/usr/local/bin/cups-recebe` (Python 3, executável): lê o job, extrai `requesting-user-name` e `job-name` do cabeçalho XPIF e chama:

```
lp -d <fila> -U <usuario> -t <titulo> -o document-format=application/postscript <arquivo>
```

Depois apaga o temporário. O log vai para o journal:

```bash
journalctl -u 'cups-recebe-adm-xerox@*'
```

O systemd abre a porta (`Accept=yes`) e inicia uma instância do serviço por conexão, como usuário `lp`. Arquivos prontos em [`configs/systemd/`](../configs/systemd/) e o código em [`scripts/server/cups-recebe`](../scripts/server/cups-recebe). Para outra fila: copie o par `.socket`/`@.service` trocando a porta (9102...) e o nome da fila.

**Firewall:** o `cupsd.conf` não vale para essa porta. Neste projeto o `ufw` estava inativo, então a restrição foi feita no próprio socket com `IPAddressDeny=any` e `IPAddressAllow=` para as sub-redes de usuários (drop-in `ip.conf`).

**Teste sem papel:**

```bash
cupsdisable adm-xerox
nc -w 5 127.0.0.1 9101 < amostra.ps
journalctl -u 'cups-recebe-adm-xerox@*' --since "5 min ago"
lpstat -o adm-xerox
cancel -a adm-xerox
cupsenable adm-xerox
```

## Controle de cor e de acesso por grupo do AD

Grupos criados no Samba AD (na OU de grupos):

```bash
/usr/local/samba/bin/samba-tool group add Impressora_ADM_Xerox \
    --groupou="OU=grupos,OU=EMPRESA" --group-scope=Global --group-type=Security
/usr/local/samba/bin/samba-tool group add Impressora_ADM_Xerox_Cor \
    --groupou="OU=grupos,OU=EMPRESA" --group-scope=Global --group-type=Security
```

- `Impressora_ADM_Xerox`: quem usa a impressora (P&B).
- `Impressora_ADM_Xerox_Cor`: também pode imprimir colorido. Quem está no `_Cor` também conta como autorizado a usar a impressora.
- O servidor enxerga os grupos pelo winbind (`id usuario`). O cache do winbind pode demorar alguns minutos para atualizar; `net cache flush` força.

O bloqueio por usuário nativo do CUPS (`lpadmin -u allow:@grupo`) não funcionou com winbind; o controle ficou no filtro e na GPO.

## GPO "Impressora - CUPS"

Em vez de uma fila "do usuário", o desenho usa uma **tarefa agendada de computador** (Preferências da GPO) que roda um script no logon:

- GPO vinculada à OU dos computadores que participam do piloto; filtro de segurança por **grupo de computadores** (`Impressora_CUPS_PCs`) em vez de listar PCs um a um (mantendo "Authenticated Users" com Leitura na Delegação).
- Tarefa `Sync-Impressoras`: ação **Atualizar**, conta **NT AUTHORITY\SYSTEM** com privilégios mais altos, disparador **Ao fazer logon, qualquer usuário, com atraso de 30 segundos** (sem atraso o usuário ainda não aparece no `Win32_ComputerSystem`), executando por demanda, interrompendo após 1 hora, sem iniciar nova instância, sem exigir rede elétrica.
- Ação: `powershell.exe -NoProfile -ExecutionPolicy Bypass -File "\\empresa.local\NETLOGON\scripts\Impressoras\CUPS\Sync-Impressoras.ps1" -ConfigPath "\\empresa.local\NETLOGON\scripts\Impressoras\CUPS\impressoras.json"`
- Scripts de PowerShell devem ser adicionados na aba **"PowerShell Scripts"** do GPMC, nunca na aba legada "Scripts" (o Windows tenta abrir o `.ps1` no Bloco de Notas em vez de executar).

### O que o `Sync-Impressoras.ps1` faz

1. Descobre o usuário do console (`Win32_ComputerSystem`) e consulta seus grupos no AD via ADSI (`memberof`).
2. Lê o `impressoras.json` (uma entrada por impressora: `nome` amigável, `driver`, `pastaDriver`, `porta` (nome da porta TCP no Windows), `host`, `portaTcp`, `grupoAcesso` e `grupoCor`). Exemplo em [`configs/impressoras.json.example`](../configs/impressoras.json.example); o script está em [`scripts/windows/Sync-Impressoras.ps1`](../scripts/windows/Sync-Impressoras.ps1). Para uma nova impressora, acrescente um objeto ao JSON.
3. Para cada impressora: permitido = grupo de acesso **ou** grupo de cor. Se permitido, instala o driver (`pnputil` da pasta + `Add-PrinterDriver`), cria a porta TCP, cria a fila já com o **nome final** (nunca criar e renomear: `Rename-Printer` zera os padrões do driver), aplica P&B como padrão e liga o PIN. Se não permitido, remove.
4. **Limpeza opcional** das demais impressoras: só para usuários dos grupos de impressão, remove todas as impressoras exceto as do JSON permitidas e "Microsoft Print to PDF", e depois as portas de rede órfãs. Há salvaguardas (só roda se o usuário tem direito a pelo menos uma impressora do JSON e todas as permitidas existem naquele momento; erro de AD não altera nada) e um modo `-SimularLimpeza` que só registra no log.
5. Escreve um log em `C:\ProgramData\<pasta>\sync.log`.

Limitação: o script roda como SYSTEM, então só enxerga as impressoras da máquina. Conexões por usuário (`\\servidor\fila`, `http://...` no contexto do usuário) não são removidas.

### Ligar o PIN como padrão

No print ticket padrão do driver: `pskv11:JobPasscode` = `psk:On` **mais** um `ParameterInit pskv11:JobPasscodeString` com valor vazio (só o `psk:On` é ignorado pelo driver). Resultado: o aplicativo mostra "Impressão protegida por PIN: Ativado" com o campo vazio, e o Windows não deixa imprimir sem digitar um PIN (usar 6 dígitos). Quem desligar o PIN tem o job rejeitado pelo servidor (filtro v3).

### Comandos de referência no Windows (PowerShell elevado)

```powershell
pnputil /add-driver "<pasta-do-driver>\*.inf" /install
Add-PrinterDriver -Name "Xerox AltaLink C8030 V4 PS"
Add-PrinterPort -Name "IP_192.0.2.10_9101" -PrinterHostAddress "192.0.2.10" -PortNumber 9101
Add-Printer -Name "Xerox Altalink - ADM" -DriverName "Xerox AltaLink C8030 V4 PS" -PortName "IP_192.0.2.10_9101"
Set-PrintConfiguration -PrinterName "Xerox Altalink - ADM" -Color $false
```

Dica: não cole o `PrintTicketXML` inteiro (dezenas de KB em base64) em chat; compare antes/depois com `Compare-Object` e mostre só as linhas diferentes.

### Onde ficam os arquivos

- Driver (pacote da Xerox, **não incluído neste repositório**; baixe do site oficial): em uma pasta compartilhada de leitura para **Domain Computers** (o script roda como SYSTEM). Neste projeto foi usada uma subpasta no `NETLOGON` do DC.
- Script e JSON: no mesmo `NETLOGON`.
- **Escrever no `NETLOGON` só como administrador do domínio** (pela VM do RSAT); o usuário comum só lê.
- **Atenção:** o SYSVOL guarda também todas as GPOs. Faça **backup do SYSVOL (com permissões)** antes de atualizar o Samba, principalmente se ele foi instalado por tarball.
