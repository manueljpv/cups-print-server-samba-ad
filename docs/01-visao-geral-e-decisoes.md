# Visão geral e decisões de projeto

> Todos os nomes, endereços e usuários deste documento são fictícios (veja o aviso no README).

## Objetivo

Construir do zero um servidor de impressão **CUPS em Linux** para uma empresa que usa um domínio **Samba AD**, de forma que:

- as impressoras de rede (alugadas) continuem funcionando com **impressão protegida por PIN** da Xerox;
- cada impressão seja **contabilizada** por usuário, fila, páginas, cópias, frente e verso e **cor (P&B x colorido)**, porque o contrato de locação cobra **por face impressa**, com valores diferentes por cor;
- as impressoras cheguem aos usuários **automaticamente por GPO**, e cada usuário veja apenas as que pode usar;
- só quem for autorizado possa imprimir em cores.

## Ambiente de referência (fictício)

| Item | Valor de exemplo |
|---|---|
| Domínio | `empresa.local` (Samba AD, instalado por tarball) |
| Controlador de domínio | `dc01` (`192.0.2.5`) |
| Servidor de impressão | `srv-cups` (`192.0.2.10`), Ubuntu Server 24.04 LTS, VM no Proxmox (2 vCPU, 4 GB RAM, 32 GB) |
| Impressora colorida | Xerox AltaLink C8030 (`192.0.2.20`), fila `adm-xerox` |
| Clientes | Windows 11, domínio `empresa.local`, em três sub-redes (`192.0.2.0/24`, `198.51.100.0/24`, `203.0.113.0/24`) |

## Decisões

1. **CUPS em vez de Windows Print Server.** Não há orçamento para licenças de Windows Server e CALs.
2. **VM separada** para o servidor de impressão (Ubuntu 24.04 LTS).
3. **Fila com filtro próprio de contagem.** O CUPS entrega o arquivo da impressão **intacto** à impressora (o PIN é preservado) e um filtro em Python grava a contabilidade lendo o cabeçalho do próprio arquivo do job. Detalhes em [02-filtro-de-contagem.md](02-filtro-de-contagem.md).
4. **Driver Xerox AltaLink C8030 V4 PS** nos clientes. O PCL6 não serve (o CUPS não o converte e o filtro depende de PostScript com cabeçalho XPIF).
5. **Entrega por porta TCP RAW** no servidor (uma porta por fila, ex.: 9101), com um receptor que entrega o job ao CUPS. Detalhes em [03-entrega-por-gpo.md](03-entrega-por-gpo.md).
6. **Cobrança por face.** Como o contrato conta faces, o que o filtro registra (páginas x cópias) é a base da fatura, e o frente e verso padrão do driver não distorce a contagem.
7. **Autenticação no painel da impressora via LDAP/Kerberos contra o Samba AD** foi deixada como "carta na manga" para depois: exige muitos testes e não pode falhar.
8. **`cups-browsed` desativado e mascarado.** Ao abrir o CUPS para a rede, ele criou filas automáticas indesejadas.

## Padrão de nomes das filas

`local-marca`, pelo **lugar** (não pelo modelo), sem acento nem espaço. Exemplos: `adm-xerox`, `prod-canon`, `fat-canon`.

O nome entra no endereço da fila, na coluna "fila" do log de contabilidade e na GPO. Trocá-lo depois divide o histórico. Dois equipamentos no mesmo local: acrescentar número (`prod-canon-2`). Descrição (`-D`) e local (`-L`) são texto livre.

Padrão de grupos no AD: `Impressora_<LOCAL>_<MARCA>` (quem usa, P&B) e `Impressora_<LOCAL>_<MARCA>_Cor` (também pode colorido).

## Por que não as alternativas (testes)

Mesmo PDF de 4 páginas, enviado de um cliente Windows:

| Fila / driver no Windows | PIN do driver | Páginas contadas | Cor x P&B no log |
|---|---|---|---|
| IPP Everywhere + driver genérico Microsoft (PWG Raster) | sem opção de PIN | só 1 | vazio |
| IPP Everywhere + Xerox V4 PS | opção aparece, mas **PIN perdido** | **4 (correto)** | vazio |
| Fila raw + Xerox V4 PS | **PIN funciona** | conta **1 por job** | vazio |

Conclusões:

- O driver Xerox embute PIN e modo de cor no próprio arquivo de impressão. Na fila IPP Everywhere o CUPS converte o arquivo e descarta isso; na fila raw ele passa intacto, mas o CUPS não conta páginas.
- O atributo `print-color-mode` só aparece no `page_log` quando o cliente o envia como atributo IPP, e os drivers do Windows não enviam.
- Filas raw e drivers PPD são marcados como obsoletos pelo CUPS. No CUPS 2.4 (Ubuntu 24.04) isso não afeta hoje, mas é um risco de longo prazo.
- O driver Linux oficial da Xerox é genérico (sem cor nem PIN). O aplicativo SmartStart não é necessário.

A solução foi um **filtro** que preserva o arquivo e grava uma **contabilidade própria**.

## Limitações conhecidas (documentar no relatório)

- A contagem é feita **no envio**. Um job cancelado depois (no painel, ou antes de liberar o PIN) continua contado.
- Cor e cópias refletem o que o driver pediu, não uma análise página a página.
- O nome do usuário vem do Windows e não é validado pelo servidor.
- Se o driver gerar uma folha de identificação por job, ela não entra na contabilidade (o filtro não a vê) mas pode entrar na cobrança. Nos testes não saiu folha extra.
- Filas raw e PPD estão marcados como obsoletos pelo CUPS.
