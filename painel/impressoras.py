"""Cadastro das impressoras que o painel conhece (usado pela pagina de permissoes).

Os valores abaixo sao FICTICIOS (exemplo): troque nomes, IPs, locais e grupos pelos do seu ambiente.

Para incluir uma impressora nova, basta acrescentar um bloco em IMPRESSORAS:
  - id:        identificador curto, sem espacos (usado na URL)
  - nome/modelo/ip/local: texto mostrado na pagina
  - niveis:    do MAIOR para o MENOR acesso. Cada nivel aponta para um grupo do AD
               (nome do grupo, sem maiusculas/minusculas). Impressora sem cor/P&B
               tem um nivel so (ex.: "Imprimir").
               'pilula' define a cor da etiqueta: cor | info | ok
  - grupo_pcs: grupo do AD com os computadores liberados nessa impressora (filtro da GPO)
Grupo que nao existir no AD aparece como aviso na pagina (nao quebra nada).
Mais adiante a pagina de cadastro de impressoras (com drivers) vai escrever aqui.
"""

IMPRESSORAS = [
    {"id": "adm-xerox", "nome": "adm-xerox", "modelo": "Xerox AltaLink C8030",
     "ip": "192.0.2.20", "local": "Prédio Administrativo",
     "niveis": [
         {"id": "cor", "rotulo": "Colorido", "grupo": "Impressora_Xerox_ADM_Cor", "pilula": "cor"},
         {"id": "pb", "rotulo": "Só P&B", "grupo": "Impressora_Xerox_ADM", "pilula": "info"},
     ],
     "grupo_pcs": "Impressora_Xerox_ADM_PCs"},
    {"id": "producao-canon1", "nome": "producao-canon1", "modelo": "Canon 1643IF",
     "ip": "192.0.2.21", "local": "Sala da Produção",
     "niveis": [{"id": "imp", "rotulo": "Imprimir", "grupo": "Impressora_Canon1_Producao", "pilula": "info"}],
     "grupo_pcs": "Impressora_Canon1_Producao_PCs"},
    {"id": "producao-canon2", "nome": "producao-canon2", "modelo": "Canon 1643IF",
     "ip": "192.0.2.22", "local": "Sala da Produção",
     "niveis": [{"id": "imp", "rotulo": "Imprimir", "grupo": "Impressora_Canon2_Producao", "pilula": "info"}],
     "grupo_pcs": "Impressora_Canon2_Producao_PCs"},
    {"id": "doca-canon", "nome": "doca-canon", "modelo": "Canon 1643IF",
     "ip": "198.51.100.30", "local": "Doca de Expedição",
     "niveis": [{"id": "imp", "rotulo": "Imprimir", "grupo": "Impressora_Canon_Doca", "pilula": "info"}],
     "grupo_pcs": "Impressora_Canon_Doca_PCs"},
    {"id": "faturamento-hp", "nome": "faturamento-hp", "modelo": "HP M428",
     "ip": "198.51.100.31", "local": "Faturamento",
     "niveis": [{"id": "imp", "rotulo": "Imprimir", "grupo": "Impressora_HP_Faturamento", "pilula": "info"}],
     "grupo_pcs": "Impressora_HP_Faturamento_PCs"},
]
