# Roadmap

**Português** · [English](ROADMAP.en.md) · [Español (Honduras)](ROADMAP.es-HN.md)

Este documento mostra para onde o projeto pode ir e o que aprendemos até aqui. Nada abaixo é promessa de data: são intenções, em ordem aproximada de prioridade. Sugestões são bem-vindas por *issue*.

## Concluído recentemente

- **Troca controlada da senha da conta de máquina.** A causa do incidente do winbind foi confirmada por reprodução e a troca automática do Samba foi substituída por uma troca agendada, com reinício do winbind, quatro testes e um status em JSON. Veja o [doc 06](docs/06-troca-controlada-winbind.md).
- **Painel web interno** com login do AD (LDAPS), sessões e acesso por grupo: página de **controle do winbind**, página de **permissões de impressão** (somente leitura, por usuário, departamento, impressora e computador) e um alerta para uma tela de parede. Veja o [doc 07](docs/07-painel-web.md).
- **Cadastro de várias impressoras no painel**, com grupos de acesso, de cor e de computadores por impressora, no padrão `Impressora_<Marca>_<Local>`.

## Curto prazo

**Contabilidade e relatórios**

- **Relatório mensal.** Ler `contagem-AAAA-MM.log` e gerar o total por impressora, por departamento e por usuário, separando P&B e colorido e aplicando as tarifas por face do contrato. O relatório deve tratar as colunas 10 a 12 do log como opcionais, ignorar na soma as linhas `rejeitado-sem-pin` e não ler os arquivos `.teste.log`.
- **Grupos por departamento no AD.** Hoje só existem grupos de acesso e de cor por impressora. Sem grupos por departamento, o relatório por departamento não fecha.
- **Painel de controle web (HTML).** Uma página acessível pelo navegador, com a contagem de impressões sempre **mensal**, para manter o histórico e permitir comparar meses e anos. Mostra o total da empresa e o total **por impressora, por departamento e por pessoa** (P&B x colorido); para cada pessoa, o que ela imprimiu, com o **nome dos arquivos**, dia e hora; e uma visão mês a mês para comparativos. Inclui uma lista dos jobs rejeitados por falta de PIN, já que a porta RAW não consegue avisar o usuário na tela.
- **Painel: etapa 2 e página de impressões.** Botões que alteram os grupos do AD por uma conta delegada (só a pertença dos grupos `Impressora_*`), com auditoria de quem, quando e o quê; cruzamento com o inventário (GLPI) para confirmar qual computador é de cada usuário; revisão de acessos (quem tem cor e nunca imprimiu colorido, quem não imprime há 90 dias); e a página de controle de impressões (relatórios, custos, franquia), hoje apenas um esqueleto.
- **Verificação de uso pessoal.** Sinalizar, a partir do nome dos arquivos, impressões que pareçam pessoais (por exemplo, por palavras e padrões configuráveis), para **revisão humana**, sem bloquear a impressão. Como isso envolve o nome dos documentos de cada pessoa, restrinja o acesso ao painel e à contabilidade a quem precisa, e deixe a política de impressão clara para os usuários (verifique também as exigências de privacidade aplicáveis, como a LGPD).
- **Custos e franquia no painel.** Como as impressoras são alugadas, cada página tem um custo. O painel deve permitir cadastrar, **por impressora**, o preço da página P&B e o da página colorida (que podem variar de uma impressora para outra) e calcular o custo de cada mês: por impressora, **por departamento** (base para um eventual rateio) e por pessoa. Os contratos costumam ter uma **franquia**: por exemplo, a Xerox pode imprimir até 1.000 páginas coloridas a um preço, e a partir da 1.001ª o valor sobe. O painel deve cadastrar a franquia e o preço excedente por impressora e por cor, mostrar um **contador do consumo da franquia no mês** (quanto já foi usado e quanto resta) e avisar quando o consumo se aproximar do limite. Guardar as tarifas **com data de vigência**, para que meses antigos não mudem quando o contrato mudar, e definir como o custo excedente é rateado entre departamentos. Confira no contrato se a franquia é por impressora, por cor ou compartilhada. Até ser conferida com os contadores da impressora, a contagem do servidor é uma estimativa (ela é feita no envio, e jobs cancelados continuam contados).
- **Fazer o filtro informar `PAGE: total N` ao CUPS**, para que o `page_log` fique coerente com a contabilidade própria (hoje mostra `total 0` nas filas com filtro).
- **Conferir dois pontos do driver e do contrato:** se o ID do trabalho (`JobIdBannerOn`) gera folha extra em algum cenário, e como a locadora cobra cada modo de cor (incluindo um possível modo automático).

**Servidor**

- **Cadastrar as demais impressoras** (outras Canon e uma HP). Para cada uma: fila `local-marca`, receptor em outra porta, entrada no mapa de cor e uma linha no `impressoras.json`. Antes de reaproveitar o filtro, testar o que o driver de cada marca grava no arquivo do job. Elas já constam no cadastro do painel; faltam a fila, o receptor, o driver e a entrega por GPO.
- **Testes automatizados do filtro e do receptor** com amostras de job sintéticas (P&B, colorido, com e sem PIN, usuário dentro e fora do grupo de cor), para validar sem impressora e sem gastar papel.
- **Rotina de backup do SYSVOL** (com permissões) antes de atualizar o Samba, principalmente se ele foi instalado por tarball.

**GPO e clientes Windows**

- **Ampliar o piloto por fases.** Hoje o escopo é a equipe de TI, filtrada por um grupo de computadores. Ampliar para outros departamentos, adicionando computadores ao grupo, depois de validar com cada equipe.
- **Limpar conexões por usuário.** O script roda como `SYSTEM` e só enxerga as impressoras da máquina; conexões do contexto do usuário (`\\servidor\fila`, `http://...`) ficam. Uma versão futura deve limpar `HKU\<SID>\Printers\Connections` do usuário logado.
- **Limpar o legado.** Apagar o grupo antigo, a pasta do driver PCL6 e os scripts antigos da GPO anterior no `NETLOGON`.
- **Desligar o `JobIdBannerOn` no padrão do driver, por precaução**, depois de descobrir a chave de "desligado" comparando o print ticket antes e depois.
- **Testar em um PC realmente limpo**, sem a "Internet Port" fantasma que ficou presa no PC de teste.
- **Entrada em produção.** Arquivar e zerar o log de testes para começar a contabilidade limpa (veja o [doc 04](docs/04-problemas-comuns.md)).

## Longo prazo

- **Autenticação no painel da impressora via LDAP/Kerberos contra o Samba AD**, dispensando o PIN e identificando o dono de cada job. É a "carta na manga" do projeto: exige muitos testes e não pode falhar. Testar em uma fila separada, sem mexer na fila que já funciona, e avisar a locadora antes de mexer na impressora alugada. O usuário do job precisa bater com o login do domínio, e a compatibilidade LDAP do Samba AD (bind, LDAPS, certificado) precisa ser confirmada.
- **Validar o usuário do job.** Hoje o nome vem do Windows e o servidor não o valida. A autenticação acima resolveria isso na origem.
- **Contagem na saída do papel.** Hoje a contagem é feita no envio, então um job cancelado depois continua contado. Reconciliar com os contadores da própria impressora (SNMP ou contabilidade da Xerox) para conferir a fatura da locadora.
- **Sair das filas raw e dos drivers PPD**, que o CUPS marca como obsoletos e deixarão de funcionar numa versão futura (CUPS 3.x). Avaliar uma arquitetura que preserve PIN e contagem sem depender deles.
- **Página para adicionar e remover impressoras no painel.** Parte sensível, que precisa de planejamento próprio, principalmente para tratar o **driver** de cada impressora.
- **Painel em tela dedicada** (por exemplo, um notebook Linux com navegador mostrando vários painéis), para que os avisos sejam vistos sem depender de alguém abrir a página.
- **Mais marcas de impressora**, com um filtro que entenda o cabeçalho de cada driver.
- **Empacotamento e automação** da instalação do servidor (script ou Ansible), para reproduzir o ambiente mais rápido.
- **Traduzir a pasta `docs/`** para inglês e espanhol de Honduras.

## Lições aprendidas

1. **Teste antes de escolher a arquitetura.** Três filas de teste com o mesmo PDF mostraram que nenhuma sozinha servia: a IPP conta mas perde o PIN, e a raw mantém o PIN mas conta 1 por job. A solução (um filtro) só apareceu depois de olhar o que cada caminho realmente entregava.
2. **Abra o arquivo do job.** Ligar `PreserveJobFiles` por um momento e inspecionar o arquivo revelou que o driver já embute PIN, cor, lados e usuário num cabeçalho XML. Tudo o que o relatório precisava estava ali, sem depender de atributos IPP que o Windows não envia.
3. **Entenda o contrato antes de contar.** A locação cobra por face, não por folha. Isso definiu o que o filtro conta (páginas x cópias) e tirou a preocupação com o frente e verso padrão.
4. **A ferramenta de teste precisa representar o caminho real.** O `cupsfilter` na linha de comando não reproduz a cadeia de filtros do `cupsd`. Uma fila de teste com `socket://127.0.0.1:...`, um `nc` capturando a saída e o `lp` reproduzem o que acontece de verdade, sem gastar papel.
5. **Procure a causa raiz.** O job de um usuário saía com 40 páginas de código porque o CUPS o classificou como `text/plain` (a regra de PostScript só olha os primeiros ~128 bytes) e descartou o cabeçalho. Duas linhas `*cupsFilter` no PPD resolveram; mexer no driver não teria resolvido.
6. **Registre o que foi pedido e o que saiu.** Gravar a cor pedida, a cor efetiva e uma nota por job permitiu separar "o usuário pediu P&B" de "o servidor forçou P&B" quando todos os usuários passaram a sair em preto e branco.
7. **Dependências de identidade precisam de monitoramento.** A troca automática da senha da conta de máquina, 7 dias após o ingresso no domínio, deixou o winbind sem enxergar os grupos. A falha foi silenciosa e parecia um problema de cor. Eventos periódicos como esse merecem aviso. Isso foi resolvido com a troca controlada (veja o [doc 06](docs/06-troca-controlada-winbind.md)).
8. **Falhe de forma segura e visível.** Se o log não grava, o job segue para a impressora; se a consulta de grupos falha, o job sai em P&B. Mas uma pasta com dono errado faz o log parar sem erro, então vale monitorar o que o filtro depende para gravar.
9. **Teste o caminho do cliente, não só o do servidor.** Instalar por URL IPP e por compartilhamento Samba falhou no Windows por motivos diferentes (porta "Internet Port", driver V4, erro 0x80070005), e só os testes em PCs reais mostraram isso. A porta TCP RAW foi a que funcionou.
10. **A ordem importa no Windows.** `Rename-Printer` zera as preferências do driver; criar a fila já com o nome final e só depois aplicar os padrões evita perder o PIN e o P&B.
11. **O PowerShell "como administrador" pode não ser o usuário do domínio.** Ele não via o AD nem o `NETLOGON`. Testar como `SYSTEM`, por uma tarefa agendada, reproduz o que a GPO vai executar.
12. **Automação que apaga precisa de salvaguardas.** A limpeza de impressoras só roda se o usuário tem direito a alguma impressora do cadastro e todas as permitidas existem; erro de AD não altera nada; e um modo de simulação registra no log o que seria removido antes de remover.
13. **Piloto pequeno, reversível e documentado.** A GPO nova nasceu para dois computadores, depois um grupo de computadores. As GPOs antigas foram salvas antes de serem apagadas, e apagar uma GPO não remove as impressoras já instaladas nos PCs.
14. **Teste a documentação executando-a.** Ao rodar os comandos do passo a passo num servidor, o teste achou um bug que só existia no repositório: o receptor decodificava o título em `latin-1` e quebrava os acentos, enquanto o de produção já usava UTF-8. Comparar o repositório com o que roda em produção vale o tempo.
15. **Documente enquanto faz.** Os registros de decisões, testes e incidentes permitiram retomar o trabalho entre sessões e, agora, publicá-lo.
16. **Teste o serviço que está em execução, não só um processo novo.** `net ads testjoin` e `net ads status -P` passavam enquanto o `winbindd` em execução falhava no Kerberos. O teste que importa é o que o serviço de verdade enxerga.
17. **Dê à ferramenta de operação o mínimo de poder.** O painel entra com a senha do próprio usuário, lê o AD com uma conta sem escrita e a única ação com privilégio (a troca da senha da máquina) passa por uma regra do polkit que libera uma só unit do systemd.
