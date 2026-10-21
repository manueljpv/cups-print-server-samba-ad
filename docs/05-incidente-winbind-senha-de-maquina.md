# Estudo de caso: todos os usuários saindo em P&B (winbind sem grupos)

> Dados fictícios.

> **Atualização:** a hipótese abaixo foi **confirmada por reprodução** e a solução foi implantada (troca automática desligada e troca controlada, com reinício do winbind e testes). Este documento preserva o registro do incidente como aconteceu; a causa confirmada, a solução e a instalação estão em [`06-troca-controlada-winbind.md`](06-troca-controlada-winbind.md).

## Sintoma

Usuários autorizados a imprimir em cores passaram a imprimir em P&B, inclusive a página de teste. O PC pedia `color`, o filtro forçou P&B (`forcado-pb` no log). A nota `forcado-pb-erro-grupos` **não** apareceu: a consulta `id` funcionou, mas voltou sem os grupos de impressão.

## Cronologia (resumida)

- No dia da criação, a conta de máquina `SRV-CUPS$` foi criada no AD (ingresso no domínio).
- Exatamente **7 dias depois**, a senha da conta de máquina foi trocada (`pwdLastSet`). É o padrão do Samba (`machine password timeout` = 604800 s); o `smb.conf` não definia essa opção.
- Minutos depois, o journal do winbind passou a registrar `kerberos_kinit_password SRV-CUPS$@EMPRESA.LOCAL failed: Preauthentication failed`, a cada consulta de grupos.
- Por algumas horas os grupos ainda vinham do cache do winbind. Quando o cache expirou, todos os jobs coloridos passaram a ser forçados a P&B.
- Um `systemctl restart winbind` resolveu: `id` voltou a mostrar os grupos e as falhas pararam.

## Diagnóstico (o que funcionou)

1. Olhar as últimas linhas do log de contabilidade: as colunas cor efetiva, cor pedida e nota separam falha do PC de falha do servidor.
2. `id usuario` no servidor: só `domain users`, sem os grupos de impressão (inclusive para o administrador).
3. `samba-tool group listmembers <grupo>` **no DC**: membros corretos no AD. (Esse comando não existe no servidor de impressão.)
4. `wbinfo -t` ok; `wbinfo --group-info=<grupo>` ok; `wbinfo -r usuario` sem o GID do grupo: o winbind não recebia a associação. `net cache flush` não resolveu.
5. `journalctl -u winbind --since "..." | grep -a Preauth | cut -c1-12 | uniq -c`: mostra as falhas por minuto.
6. `net ads testjoin` = "Join is OK"; `net ads status -P` funciona depois do reinício.
7. No DC: `samba-tool computer show SRV-CUPS | grep -i -E 'pwdLastSet|whenChanged|whenCreated'`.

## Solução aplicada

`systemctl restart winbind` no servidor de impressão.

## Causa provável na época (depois confirmada: veja o doc 06)

A troca automática da senha da conta de máquina ocorreu e o winbind em execução continuou usando a senha antiga no Kerberos. Não se sabe por que ele não pegou a senha nova sozinho (pode ser comportamento da versão do Samba do Ubuntu). Sem o reinício, o problema volta a cada ciclo de 7 dias.

## Decisão tomada na época (superada: veja o doc 06)

- Manter a troca automática por enquanto e **não alterar o `smb.conf` agora**.
- Construir o painel de controle (relatório de impressões) com um cartão de **saúde do servidor**: avisa a próxima troca de senha e verifica se o winbind enxerga os grupos de impressão (usuário de teste, falhas de Kerberos no journal).
- Depois de testar o aviso, decidir se desliga a troca automática (`machine password timeout = 0` na seção `[global]`, com backup do `smb.conf` e reinício do winbind) e passa para troca manual periódica (`net ads changetrustpw` + reinício do winbind + teste). **Antes disso, testar se a troca manual não sofre do mesmo defeito.**
- Ideia: um botão no painel que confirma a troca, dispara o comando, testa e mostra o resultado. Cuidados: autenticação, comando fixo e restrito (sem entrada livre), registro de quem acionou, e não deixar o botão em uma tela de parede sem login.

## Ponte até a solução ficar pronta (histórico)

Na data prevista da próxima troca (7 dias depois da última), ou na primeira reclamação de P&B, conferir `id usuario` e, se faltarem os grupos de impressão, rodar `systemctl restart winbind`.

## Lições

- Um filtro que depende de um serviço de identidade precisa de **monitoramento do próprio serviço** (a falha foi silenciosa e parecia um problema de configuração de cor).
- Registrar a **cor pedida e a cor efetiva** no log permitiu distinguir "o usuário pediu P&B" de "o servidor forçou P&B".
- Datas de rotação automática de credenciais de máquina são eventos operacionais que merecem aviso.
