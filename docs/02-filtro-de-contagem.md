# Filtro de contagem (PIN + contabilidade + controle de cor)

> Dados fictícios. Nomes, IPs e usuários são exemplos.

## Problema

Era preciso **PIN do driver Xerox + contagem de páginas + distinção P&B/colorido**. A fila IPP perde o PIN; a fila raw mantém o PIN mas não conta páginas; o `page_log` só registra atributos IPP que o cliente envia. A solução é uma fila com um **filtro próprio**, que entrega o PostScript intacto e grava a contabilidade lendo o arquivo do job.

## O que o filtro lê (cabeçalho do arquivo do job)

O driver Xerox V4 PS gera no início do arquivo comandos PJL e um bloco XML no formato XPIF (linhas `@PJL XCPT`), seguido de `@PJL ENTER LANGUAGE=POSTSCRIPT` e do PostScript.

| Campo | Onde está | Uso |
|---|---|---|
| `color-effects-type` | cabeçalho XPIF | `monochrome-grayscale` ou `color` (modo escolhido no driver) |
| `sides` | cabeçalho XPIF | `one-sided`, `two-sided-long-edge` etc. |
| `copies` | cabeçalho XPIF | cópias |
| `requesting-user-name` | cabeçalho XPIF | usuário (login do Windows) |
| `job-name` | cabeçalho XPIF | título do documento |
| `job-password` | cabeçalho XPIF | PIN codificado (`xerox-simple-1`); o filtro só verifica se existe |
| `%%Pages: N` | final do PostScript | páginas (no início vem `(atend)`) |

Total cobrado = páginas x cópias.

## Evolução do filtro

- **v1 (contagem):** passa o arquivo intacto e grava usuário, fila, páginas, cópias, lados e cor.
- **v2 (controle de cor por grupo):** se o job pede `color` e o usuário **não** está no grupo `..._Cor` (ou a consulta falha), o filtro troca no cabeçalho `color-effects-type` de `color` para `monochrome-grayscale`. A impressão sai em P&B sem perder o trabalho. Fila fora do mapa de grupos = cor livre. Os grupos são consultados com `id -nG` (o `getent group` pode mostrar listas vazias com winbind). Nos demais casos o arquivo passa idêntico (md5 igual ao original, validado).
- **v3 (PIN obrigatório):** para filas na lista `FILAS_PIN`, se o job vier **sem PIN** (campo `job-password` ausente ou vazio) ele é **rejeitado em silêncio**: nada é enviado, nenhuma página é contada, o log registra `rejeitado-sem-pin`. Se a detecção falhar, o job passa. Como a porta RAW é de mão única, não há como avisar o usuário na tela; a ideia é um painel de controle que mostre essas rejeições.

> O código completo da versão atual (v3, que inclui a v1 e a v2) está em [`scripts/server/xerox-contagem`](../scripts/server/xerox-contagem). As constantes `GRUPOS_COR` e `FILAS_PIN` no topo do arquivo são o que você ajusta para cada fila. Veja o [ROADMAP](../ROADMAP.md) para os próximos passos.

## PPD mínimo

A fila usa um PPD mínimo, publicado em [`configs/xerox-contagem.ppd`](../configs/xerox-contagem.ppd) (cabeçalho PPD 4.3, `ColorDevice True`, `LanguageLevel 3`, tamanhos A4 e Carta; o `ModelName` não pode ter parênteses, o `cupstestppd` rejeita). As linhas-chave são **duas**:

```
*cupsFilter: "application/postscript 0 xerox-contagem"
*cupsFilter: "text/plain 0 xerox-contagem"
```

A segunda existe porque o CUPS, às vezes, classifica o job do Windows como `text/plain` (veja [04-problemas-comuns.md](04-problemas-comuns.md)).

## Instalação no servidor

```bash
# filtro (dono root, executável)
install -o root -g root -m 755 scripts/server/xerox-contagem /usr/lib/cups/filter/xerox-contagem

# pasta da contabilidade (dono lp)
mkdir -p /var/log/cups-contabilidade
chown lp:lp /var/log/cups-contabilidade
chmod 750 /var/log/cups-contabilidade

# fila (trocar nome, descrição, local e IP para cada impressora)
lpadmin -p adm-xerox -E -v ipp://192.0.2.20/ipp/print \
        -P configs/xerox-contagem.ppd \
        -L "Prédio Administrativo" -D "Xerox AltaLink C8030 - ADM" \
        -o printer-is-shared=true
```

## Formato do log

Um arquivo por mês: `/var/log/cups-contabilidade/contagem-AAAA-MM.log` (sem logrotate; o desenho mensal evita que os primeiros jobs de 1º de janeiro caiam no arquivo do ano anterior). Campos separados por **TAB**:

1. data/hora
2. fila
3. job
4. usuário
5. páginas
6. cópias
7. lados
8. cor **efetiva** (a que saiu)
9. título
10. cor pedida *(v2+)*
11. nota *(v2+)*: `ok`, `forcado-pb`, `forcado-pb-erro-grupos`, `FALHA-forcar-pb`, `erro-filtro`, `rejeitado-sem-pin`
12. pin *(v3)*: `sim`, `vazio`, `ausente`

Linhas antigas têm 9 ou 11 colunas: um relatório deve tratar as colunas 10 a 12 como opcionais e ignorar na soma as linhas `rejeitado-sem-pin` (páginas `?`). Exemplo (valores fictícios, colunas separadas por TAB):

```
2026-01-15 10:02:11  adm-xerox  101  usuario.a  4  1  two-sided-long-edge  monochrome-grayscale  Relatorio.pdf  color  forcado-pb  sim
2026-01-15 10:07:40  adm-xerox  102  usuario.b  1  3  one-sided           color                 Contrato.pdf   color  ok          sim
```

## Se a gravação do log falhar

O documento segue para a impressora mesmo assim (o erro vai só para o log de erros do CUPS). Se a pasta ou o log ficarem com dono errado (por exemplo, teste feito como root), o filtro **para de registrar em silêncio**: confira o dono `lp:lp`.

## Testando "no seco" (sem impressora)

```bash
# o arquivo deve passar idêntico
runuser -u lp -- env PRINTER=adm-xerox /usr/lib/cups/filter/xerox-contagem \
    9001 usuario.a "Teste" 1 "" < amostra.ps | md5sum
md5sum amostra.ps
```

Testes no seco gravam uma linha no log (a fila é `?` se a variável `PRINTER` não for definida); remova essas linhas depois e confira o dono.

Para validar um PPD/filtro **não use** `cupsfilter` na linha de comando: ele não representa a cadeia de filtros do `cupsd`. Use uma fila de teste apontando para `socket://127.0.0.1:9199`, um `nc -l 9199 > saida.bin` em outro terminal e `lp -d fila-teste arquivo`. A saída deve ter o mesmo md5 do arquivo original.
