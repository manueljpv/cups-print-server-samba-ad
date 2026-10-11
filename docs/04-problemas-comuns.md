# Problemas comuns e como foram resolvidos

> Dados fictícios.

## 1. Cliente recebe 403 "Proibido" ao acessar o CUPS

**Causa:** o bloco `<Location />` do `cupsd.conf` só permitia a sub-rede principal; os usuários estavam em outras sub-redes.

**Correção:** um `Allow` por faixa e reiniciar o serviço (exemplo em [`configs/cupsd-location.conf`](../configs/cupsd-location.conf)). Ao cadastrar novas sub-redes de usuários, acrescente uma linha `Allow` para cada.

## 2. Job sai com dezenas de páginas de "códigos" e sem PIN

**Sintoma:** a página de teste de um usuário imprimia ~40 folhas de texto; o PIN não funcionava; o log de contagem ficava com `?` nos campos.

**Causa:** o CUPS identificou o arquivo como `text/plain` (a regra de reconhecimento de PostScript com cabeçalho PJL/UEL só olha os primeiros ~128 bytes), converteu com `texttopdf`/`pdftops`/`gs` e **descartou o cabeçalho XPIF** (PIN, cor, lados).

**Correção:** acrescentar no PPD a linha `*cupsFilter: "text/plain 0 xerox-contagem"` ao lado da de `application/postscript`, e reaplicar com `lpadmin -p <fila> -P <ppd>`. Assim o arquivo passa intacto pelo filtro mesmo quando o CUPS confunde o tipo.

**Como validar sem gastar papel:** fila de teste com `socket://127.0.0.1:9199` e o mesmo PPD, `nc -l 9199 > saida.bin` em outro terminal e `lp -d fila-teste arquivo-do-job`. A saída deve ter o mesmo md5 do original e começar com `@PJL JOB`. (`cupsfilter` na linha de comando não serve para isso.)

## 3. "Não chegou nada na impressora"

Um job **retido para PIN** não imprime sozinho. Confira no painel da Xerox (Trabalhos > Impressão protegida > usuário) antes de culpar o driver.

## 4. Painel de configuração diferente do esperado / drivers acumulados

Um notebook com muitos pacotes de impressora antigos (Xerox Global Print Driver, PCL6, PS, HP, Kyocera, etc.) e o aplicativo **Xerox SmartStart** instalado fazia o driver abrir um painel diferente. Limpeza (PowerShell como administrador):

1. Ver o que existe: `Get-Printer | Select Name, DriverName, PortName`; `Get-PrinterDriver | Select Name, Manufacturer, InfPath`; `pnputil /enum-drivers /class Printer`.
2. Remover a fila: `Remove-Printer -Name "<nome>"`.
3. Remover a porta: `Get-PrinterPort | Where-Object { $_.Name -match '<ip>' } | Remove-PrinterPort`.
4. Remover drivers que não são da Microsoft: `Restart-Service Spooler; Get-PrinterDriver | Where-Object { $_.Manufacturer -ne 'Microsoft' } | Remove-PrinterDriver`. Se der 0x80070bb9 (driver em uso), o reinício do spooler libera.
5. Remover os pacotes do DriverStore (o `Remove-PrinterDriver` só tira o registro): prévia com `Get-WindowsDriver -Online -All | Where-Object { $_.ClassName -eq 'Printer' -and $_.ProviderName -ne 'Microsoft' } | Select Driver, OriginalFileName, ProviderName`, depois `pnputil /delete-driver <oemNN.inf>` (sem `/force`).
6. Desinstalar o SmartStart e qualquer app Xerox.
7. Reiniciar.

Se o "Windows Update" do assistente de impressora não listar o Xerox, exporte o driver de outro PC (`pnputil /export-driver oemNN.inf <pasta>`; **o número `oemNN` muda de PC para PC**) e instale por "Com Disco...".

## 5. `Rename-Printer` zera as preferências do driver

Renomear uma impressora volta o driver para colorido e sem PIN. Crie a fila **já com o nome final** e só então aplique padrões (`Set-PrintConfiguration`).

## 6. PowerShell "como administrador" não vê o domínio

Em PCs onde o administrador local é uma conta local, o PowerShell elevado roda com essa conta: não consulta o AD nem enxerga o `NETLOGON`. Para testar scripts que dependem do domínio, use uma tarefa agendada como SYSTEM (`schtasks /create ... /ru SYSTEM`, `/run`, `/delete`) ou o PowerShell normal do usuário de domínio.

## 7. Remover fila e driver logo em seguida falha (0x800700aa / 0x80070bb9)

O spooler segura os itens. Espere, tente de novo ou rode `Restart-Service Spooler` e aguarde ~20 s.

## 8. `cups-browsed` cria filas automáticas

Ao abrir o CUPS para a rede, o `cups-browsed` criou filas `implicitclass://` das impressoras vistas na rede. Solução: `systemctl disable --now cups-browsed && systemctl mask cups-browsed`. Observação: a busca automática do Windows também lista impressoras direto da rede; essas entradas **não** passam pelo CUPS e não entram na contabilidade.

## 9. `page_log` em branco no Ubuntu 24.04

O `PageLogFormat` do `cupsd.conf` vem em branco, o que desabilita o `page_log`. Defina-o (veja [`configs/cupsd-location.conf`](../configs/cupsd-location.conf)). Mesmo assim, o `page_log` não traz a cor quando o cliente é o driver do Windows e mostra `total 0` nas filas com filtro; a fonte para relatórios é o log de contabilidade.

## 10. Contabilidade parou de gravar sem erro

Pasta ou arquivo de log com dono errado (por exemplo, um teste feito como root). Confira `ls -l /var/log/cups-contabilidade/` e corrija com `chown lp:lp`.

## 11. Entrada em produção

Arquive e zere o log de testes para começar a contabilidade limpa:

```bash
mv /var/log/cups-contabilidade/contagem-AAAA-MM.log /var/log/cups-contabilidade/contagem-AAAA-MM.teste.log
install -o lp -g lp -m 600 /dev/null /var/log/cups-contabilidade/contagem-AAAA-MM.log
```

O relatório deve ler só `contagem-AAAA-MM.log`, não os `.teste.log`.
