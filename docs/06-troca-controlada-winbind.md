# Troca controlada da senha da conta de máquina (winbind)

> Dados fictícios. Este documento fecha o [estudo de caso](05-incidente-winbind-senha-de-maquina.md): lá está o sintoma e o diagnóstico; aqui estão a causa confirmada e a solução implantada.

## Resumo

O Samba troca sozinho, a cada 7 dias, a senha da conta de máquina do servidor (`SRV-CUPS$`). A troca funciona, mas **o processo `winbindd` que já estava em execução continua usando a senha antiga no login Kerberos**. Quando o cache de grupos expira, o filtro de contagem deixa de enxergar os grupos de impressora e todos os usuários saem em P&B.

A solução foi **desligar a troca automática** e fazer a troca de forma controlada: o script troca a senha, **reinicia o winbind**, testa e registra o resultado, em horário de pouco movimento.

## Causa confirmada

O que valia como hipótese no estudo de caso foi reproduzido em um servidor com Samba/winbind 4.19 (Ubuntu 24.04), em horário de pouco fluxo, forçando a troca com `sudo wbinfo --change-secret`:

1. O `winbindd` trocou a senha e verificou a nova no DC ("Verified new password remotely").
2. Minutos depois, `net ads testjoin` dizia "Join is OK" e `net ads status -P` (que roda como **processo novo**) fazia o login Kerberos sem problema. Ou seja, o DC aceita a senha nova.
3. O **mesmo `winbindd`** falhou no `kinit` com `Preauthentication failed` ao ser forçado a consultar o AD (`net cache flush && id usuario`).
4. `systemctl restart winbind` corrigiu: os grupos voltaram e o journal ficou com zero falhas.

Duas observações úteis:

- **O `testjoin` não detecta esse defeito.** Ele só valida o canal seguro (netlogon). O teste que distingue é `net ads status -P` (processo novo) contra o que o winbind em execução enxerga.
- Os comandos de teste precisam de `sudo`: o `secrets.tdb` só é legível pelo root.

## O que foi implantado

### 1. Desligar a troca automática

No `/etc/samba/smb.conf`, seção `[global]` (faça backup antes):

```
machine password timeout = 0
```

### 2. O script `troca-senha-maquina`

[`scripts/server/troca-senha-maquina`](../scripts/server/troca-senha-maquina) (Python 3, `root:root`, modo 755) tem dois modos:

| Modo | O que faz |
| --- | --- |
| `trocar` | Confere `net ads testjoin` (aborta se falhar), roda `wbinfo --change-secret`, espera 5 s, reinicia o winbind, espera ele responder, limpa o cache (`net cache flush`) e roda os testes. Se algum teste falhar, reinicia o winbind mais uma vez e testa de novo antes de registrar falha. |
| `verificar` | Só testa e atualiza o status. Não troca nem reinicia nada. Só escreve no log quando há falha. |

Os **4 testes**:

1. `net ads testjoin` responde "Join is OK".
2. `net ads status -P`: login Kerberos da conta de máquina em um processo novo.
3. `id -nG <usuário de teste>` contém o grupo de teste (o winbind em execução enxerga os grupos de impressora).
4. Zero ocorrências de `Preauthentication failed` no journal do winbind. No modo `verificar`, a janela é a mais recente entre "1 hora atrás" e "o último início do winbind" (um reinício limpo zera a contagem).

Constantes no topo do script, que você deve ajustar ao seu ambiente:

```python
CONTA = "SRV-CUPS"                    # nome da conta de máquina, sem o $
USUARIO_TESTE = "usuario.a"           # usuário do AD que deve estar no grupo de teste
GRUPO_TESTE = "impressora_xerox_adm"  # grupo (em minúsculas) em que ele deve estar
HORA_AGENDADA = 4                     # hora da troca, só para calcular a "próxima troca"
```

Se o usuário de teste sair do grupo, o teste 3 passa a falhar: troque o usuário no script.

Detalhes de funcionamento:

- **Uma execução por vez:** trava em `/run/troca-senha-maquina.lock`; a segunda execução sai com código 3.
- **Data da última troca** lida do AD: `net ads search -P '(sAMAccountName=SRV-CUPS$)' pwdLastSet`.
- **Log:** `/var/log/troca-senha-maquina.log` (sem rotação).
- **Status:** `/var/lib/troca-senha-maquina/status.json` (modo 644, gravação atômica), com `gerado_em`, `modo`, `resultado` (`ok` ou `falha`), a lista de `testes`, `ultima_troca_ad`, `dias_desde_troca`, `proxima_troca` e, depois de uma troca, `ultima_execucao_trocar`, `ultimo_resultado_trocar` e `ultima_troca_ok`. Não tem dados sensíveis: é a fonte da página de status do [painel](07-painel-web.md) e do alerta do carrossel.

### 3. Agendamento (systemd)

Units em [`configs/systemd/`](../configs/systemd):

| Timer | Quando | O que roda |
| --- | --- | --- |
| `troca-senha-maquina.timer` | `OnCalendar=Mon *-*-01..07 04:00:00`: **primeira segunda-feira de cada mês, às 04:00**. `Persistent=true`: se o servidor estava desligado, roda ao ligar. | `troca-senha-maquina trocar` |
| `troca-senha-maquina-verificar.timer` | `OnCalendar=*:07:00`: **toda hora, no minuto 7**. | `troca-senha-maquina verificar` (o serviço aceita o código 3 como sucesso) |

A segunda-feira cedo foi escolhida de propósito: a equipe chega logo depois e pode agir se algo der errado.

### 4. Botão no painel (opcional)

O [painel web](07-painel-web.md) tem uma página que mostra o status e permite disparar a troca. Como o servidor web não roda como root, uma regra do polkit ([`configs/polkit/50-painel-winbind.rules`](../configs/polkit/50-painel-winbind.rules)) permite ao usuário `painel` **iniciar somente** a unit `troca-senha-maquina.service`, e mais nada.

## Instalação

No servidor de impressão, como root:

```bash
# 1. backup e desligar a troca automática
cp -a /etc/samba/smb.conf /etc/samba/smb.conf.bak-antes-troca-controlada
nano /etc/samba/smb.conf        # acrescente "machine password timeout = 0" em [global]
testparm -s | grep -i "machine password"
systemctl restart winbind

# 2. script (ajuste as constantes do topo antes)
install -o root -g root -m 755 scripts/server/troca-senha-maquina /usr/local/bin/troca-senha-maquina
troca-senha-maquina verificar; echo $?          # 0 = tudo ok

# 3. timers
cp configs/systemd/troca-senha-maquina*.service configs/systemd/troca-senha-maquina*.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now troca-senha-maquina.timer troca-senha-maquina-verificar.timer
systemctl list-timers 'troca-senha-maquina*' --no-pager
```

> **Cuidado:** com `machine password timeout = 0`, a senha da máquina **nunca mais é trocada** sem o timer. Não deixe o servidor nesse estado sem os timers ativos.

Faça o primeiro `troca-senha-maquina trocar` à mão, com acompanhamento, antes de confiar no agendamento. Leva de 30 a 60 s e o winbind fica indisponível por alguns segundos (um job enviado nesse intervalo pode sair em P&B, porque a consulta de grupos falha).

## Operação

| Tarefa | Comando |
| --- | --- |
| Trocar agora | `sudo /usr/local/bin/troca-senha-maquina trocar` |
| Só conferir | `sudo /usr/local/bin/troca-senha-maquina verificar; echo $?` |
| Ver o status | `sudo cat /var/lib/troca-senha-maquina/status.json` |
| Ver os agendamentos | `systemctl list-timers 'troca-senha-maquina*' --no-pager` |
| Histórico da troca | `journalctl -u troca-senha-maquina.service` |
| Se a troca falhar | `systemctl restart winbind`, conferir `id usuario` e o log |

## Reverter (voltar à troca automática do Samba)

```bash
systemctl disable --now troca-senha-maquina.timer troca-senha-maquina-verificar.timer
cp -a /etc/samba/smb.conf.bak-antes-troca-controlada /etc/samba/smb.conf   # ou remova a linha "machine password timeout = 0"
systemctl restart winbind
```

## Limitações e cuidados

- O monitoramento é de hora em hora; uma falha pode levar até uma hora para aparecer no status.
- O log não tem rotação; configure `logrotate` se isso incomodar.
- A causa foi confirmada **neste ambiente e nesta versão do Samba**. Versões mais novas podem ter o problema corrigido; teste antes de abrir mão da troca controlada.
- Defina quem recebe o aviso quando o resultado ficar em `falha` (o painel e o carrossel mostram, mas ninguém é notificado por e-mail).

## Lições

- Um teste que passa com processo novo não prova que o serviço **em execução** está bem. Teste o que o serviço de verdade enxerga.
- Credenciais de máquina que giram sozinhas são eventos operacionais: dê a elas data, horário, teste e rota de volta.
