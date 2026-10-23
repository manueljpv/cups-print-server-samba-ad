# Adicionar uma impressora HP (PostScript, sem PIN e sem cor)

> Dados fictícios. Domínio `empresa.local`, DC `dc01`, servidor de impressão `srv-cups` (`192.0.2.10`), impressora HP LaserJet Pro M428f no Faturamento (`198.51.100.31`).

Este roteiro serve de modelo para qualquer impressora **sem PIN e sem cor**, como as HP e Canon deste projeto. Ele reaproveita o desenho da Xerox ([02](02-filtro-de-contagem.md) e [03](03-entrega-por-gpo.md)): o Windows manda o job para uma **porta TCP do servidor**, um **receptor** entrega o job ao CUPS e um **filtro** grava a contagem no mesmo log mensal. O que muda é como o usuário e as cópias são descobertos, porque o driver da HP não usa o formato XPIF da Xerox.

## O que o driver da HP grava no job

Driver: **HP Universal Print Driver PS** (baixar a linha "PS", não a PCL6). Em amostras capturadas no servidor:

| Campo | Onde está | Uso |
|---|---|---|
| `@PJL SET USERNAME="..."` | cabeçalho PJL | usuário (login do Windows) |
| `@PJL SET JOBNAME="..."` | cabeçalho PJL | título do documento |
| `JobAcct1`, `JobAcct2` | cabeçalho PJL | usuário e nome do PC (reserva, se faltar o `USERNAME`) |
| `%%Pages: N` | final do PostScript | páginas |
| `%%BeginNonPPDFeature: NumCopies N` | cabeçalho PostScript | cópias (se a linha não existe, é 1 cópia) |
| `/Duplex true\|false` e `/Tumble true\|false` | cabeçalho PostScript | frente e verso |

Pontos que valem registro:

- O driver **não repete as páginas** quando há cópias: 2 páginas com 3 cópias geram `%%Pages: 2` e `NumCopies 3`. Total cobrado = páginas x cópias, igual à Xerox.
- Sem PIN e sem cor: `@PJL SET GRAYSCALE=BLACKONLY`. A coluna de cor do log é sempre `monochrome-grayscale`.
- **Frente e verso não foi validado.** Nos testes, as preferências do driver não mostraram a opção e as amostras saíram com `Duplex` desligado. O formato com duplex ligado não foi capturado, então a leitura de `lados` nesse caso é a esperada pelo código, mas não foi comprovada. Isso não afeta a cobrança por face (páginas x cópias). Verifique se a sua impressora tem o módulo duplex (`ipptool ... sides-supported`).
- Alguns aplicativos simples (Bloco de Notas) às vezes não aplicam o número de cópias; é comportamento do aplicativo.

## Servidor

### 1. Filtro de contagem e receptor

- [`scripts/server/hp-contagem`](../scripts/server/hp-contagem) em `/usr/lib/cups/filter/` (root:root, 755). Entrega o arquivo **intacto** à impressora (o md5 do que sai é igual ao do que entra) e grava a linha de contagem com as mesmas **12 colunas** do log da Xerox, com cor `monochrome-grayscale`, nota `ok` e PIN `nao-aplica`. Páginas = último `%%Pages` do final do arquivo; cópias = `NumCopies` ou 1.
- Filas cujo nome **começa com `teste`** gravam em `contagem-AAAA-MM.teste.log`, que o relatório ignora. Use esse prefixo para testar sem sujar a contagem de verdade.
- [`scripts/server/cups-recebe-pjl`](../scripts/server/cups-recebe-pjl) em `/usr/local/bin/` (root:root, 755). É o `cups-recebe` da Xerox adaptado: em vez do XPIF, lê usuário e título do cabeçalho PJL (`USERNAME`/`JOBNAME`, com `JobAcct1` e `JOB NAME` de reserva), limpa o nome do usuário para `A-Za-z0-9._@-` e chama `lp -d <fila> -U <usuario> -t <titulo> -o document-format=application/postscript`.

### 2. PPD e fila

O PPD ([`configs/hp-contagem.ppd`](../configs/hp-contagem.ppd)) é o mínimo da Xerox adaptado: `ColorDevice False` e duas linhas `*cupsFilter` apontando para `hp-contagem`:

```
*cupsFilter: "application/postscript 0 hp-contagem"
*cupsFilter: "text/plain 0 hp-contagem"
```

Ele passa no `cupstestppd`. Criar a fila (a impressora aceita `application/postscript` por IPP; confira com `ipptool`):

```bash
lpadmin -p faturamento-hp -E -v ipp://198.51.100.31/ipp/print \
    -P configs/hp-contagem.ppd -D "HP LaserJet Pro M428f - Faturamento" \
    -L "Faturamento" -o printer-is-shared=false
```

O nome da fila segue o padrão `local-marca`. O servidor precisa alcançar a impressora (portas 9100 e 631); se ela estiver em outra VLAN, libere esse caminho.

### 3. Porta TCP (systemd)

Copie o par [`.socket`](../configs/systemd/cups-recebe-faturamento-hp.socket) e [`@.service`](../configs/systemd/cups-recebe-faturamento-hp@.service) para `/etc/systemd/system/`, com **uma porta nova por fila** (9102 aqui; a Xerox usa 9101), e habilite:

```bash
systemctl daemon-reload
systemctl enable --now cups-recebe-faturamento-hp.socket
```

**Todo receptor novo precisa do drop-in `ip.conf`**, que restringe quem conecta na porta ([`configs/systemd/ip.conf.example`](../configs/systemd/ip.conf.example)). Sem ele a porta fica aberta a qualquer sub-rede que alcance o servidor. Inclua as sub-redes de **todas** as VLANs dos PCs que vão imprimir.

### 4. Teste sem papel

```bash
cupsdisable faturamento-hp
nc -w 5 127.0.0.1 9102 < amostra.ps
journalctl -u 'cups-recebe-faturamento-hp@*' --since "5 min ago"
lpstat -o faturamento-hp
cancel -a faturamento-hp
cupsenable faturamento-hp
```

Depois imprima uma página real e confira a linha no `contagem-AAAA-MM.log` (páginas, cópias, lados, usuário).

## Windows (GPO)

### 1. Driver na pasta de rede

Coloque o pacote do driver em uma subpasta do `NETLOGON` (por exemplo `Impressoras\HPUPDPS`), legível por **Domain Computers**. O pacote do fabricante **não é incluído neste repositório**. A pasta da HP tem `.inf` de scanner e fax além do da impressora, por isso a entrada do JSON usa o campo `inf` (o `pnputil` instala só aquele arquivo).

### 2. Certificado do fabricante como Fornecedor Confiável

Driver de fabricante assinado por Authenticode precisa que o certificado do **assinante** esteja em **Fornecedores Confiáveis** nos PCs. Sem isso, o `pnputil` rodando como SYSTEM falha:

```
O fornecedor de um catálogo assinado Authenticode(tm) ainda não foi considerado confiável.
Pacotes de driver adicionados: 0
```

Em um PC de teste o driver instala "sozinho" só porque alguém marcou "Sempre confiar" na janela da primeira instalação; a tarefa da GPO, que não tem tela, falha.

1. Descubra o assinante do catálogo (use uma cópia **local** do `.cat`; o cmdlet pode não achar o arquivo pelo caminho de rede):

   ```powershell
   (Get-AuthenticodeSignature "C:\Temp\driver\arquivo.cat").SignerCertificate | Format-List Subject, Thumbprint, NotAfter
   ```

2. Exporte **só a parte pública** para um `.cer` e guarde-o na pasta do driver no `NETLOGON`. **Não publique o `.cer` no repositório.**
3. Na GPO, em *Configuração do Computador > Políticas > Configurações do Windows > Configurações de Segurança > Políticas de Chave Pública > Fornecedores Confiáveis*, **Importar** o `.cer`.
4. Conferir em um PC:

   ```powershell
   gpupdate /force /target:computer
   Get-ChildItem Cert:\LocalMachine\TrustedPublisher | Where-Object Thumbprint -eq '<thumbprint>'
   ```

Anote a validade (`NotAfter`) do certificado e confira se ela mudou a cada nova versão do driver.

### 3. Entrada no `impressoras.json`

Acrescente um objeto ao JSON ([`configs/impressoras.json.example`](../configs/impressoras.json.example)). Campos novos em relação à Xerox:

```json
{
  "nome": "HP LaserJet - Faturamento",
  "driver": "HP Universal Printing PS (v8.2.0)",
  "pastaDriver": "\\\\empresa.local\\NETLOGON\\Impressoras\\HPUPDPS",
  "inf": "hpcu360v.inf",
  "porta": "IP_192.0.2.10_9102",
  "host": "192.0.2.10",
  "portaTcp": 9102,
  "grupoAcesso": "Impressora_HP_Faturamento",
  "grupoPCs": "Impressora_HP_Faturamento_PCs",
  "pin": false
}
```

- `inf`: instala só esse arquivo da pasta do driver.
- `pin: false`: o script não tenta ligar o PIN (a impressora não usa).
- `grupoPCs`: o script só instala se o **computador** também estiver nesse grupo (veja abaixo). O P&B como padrão não é fatal: se o driver não aceitar, o script só registra um aviso no log.
- O `host` e a `portaTcp` são os do **servidor** (o receptor), não os da impressora.

### 4. Grupos do AD e GPO

Dois grupos por impressora, no padrão `Impressora_<MARCA>_<LOCAL>`:

```bash
/usr/local/samba/bin/samba-tool group add Impressora_HP_Faturamento \
    --groupou="OU=grupos,OU=EMPRESA" --group-scope=Global --group-type=Security
/usr/local/samba/bin/samba-tool group add Impressora_HP_Faturamento_PCs \
    --groupou="OU=grupos,OU=EMPRESA" --group-scope=Global --group-type=Security
```

- `Impressora_HP_Faturamento`: as pessoas que podem imprimir.
- `Impressora_HP_Faturamento_PCs`: os computadores que recebem a impressora.

Uma GPO só ("Impressora - CUPS") atende todas as impressoras: o script confere o grupo de PCs de cada entrada do JSON. Por isso o `_PCs` novo precisa ser **acrescentado ao filtro de segurança da GPO** (GPMC), e a GPO precisa estar vinculada à OU que contém esses computadores.

Quem gerencia os grupos pelo painel web usa as páginas de [permissões](07-painel-web.md): a pessoa entra no nível "Imprimir" e o PC em "Liberar".

## Cuidados na liberação

- **Reinicie o PC depois de incluí-lo no `_PCs`.** O grupo de computador só entra no token no reinício. Confira com `gpresult /scope computer /r`.
- A **rede do PC** precisa estar entre as sub-redes do `ip.conf` do socket.
- A primeira instalação leva cerca de 1 minuto e meio depois do logon. A impressora nova não vira padrão (o script não define); o padrão pode ficar no PDF.
- A **limpeza** do script remove todas as outras impressoras (menos "Microsoft Print to PDF") de quem tem acesso a alguma do JSON. Antes de liberar um setor, confirme com os usuários se alguma outra impressora (etiqueta, outra marca) deve ficar, e avise-os de que a impressora direta antiga some.
- Libere em **2 ou 3 ondas pequenas**, não o setor todo. Em cada PC da primeira onda, confira o `sync.log` (`Select-String ... "Limpeza|Impressora removida"`) e a primeira linha no log de contagem.
- O console de um PC pode usar um administrador local sem credencial de domínio; ele não abre o `NETLOGON`, mas o SYSTEM da tarefa abre.

## Para outras marcas (Canon e semelhantes)

Antes de repetir este roteiro: capture uma amostra do job do driver da marca, veja se a impressora aceita PostScript e onde o usuário, o título, as cópias e o total de páginas aparecem. Só então ajuste o filtro e o receptor. Importe o certificado do fabricante do driver na GPO (passo 2 acima).
