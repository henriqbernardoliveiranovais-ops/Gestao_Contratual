# Portal de Gestão Contratual

Painel executivo de contratos (vencimentos, reajustes e tratativas) com cadastro direto pelo portal,
importação/exportação de planilha Excel e gráfico de índices (IPCA, IGP-M, IPC/FIPE).

Feito com **Flask + SQLite** (mesmo esquema dos portais anteriores).

## Instalação (Windows / PowerShell)

```powershell
cd portal-contratos
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env          # depois edite a SECRET_KEY
python -m flask db upgrade      # cria o banco em instance\contratos.db
python run.py                   # abre em http://localhost:5000
```

Os colegas acessam pela rede em `http://IP-DA-SUA-MAQUINA:5000`.

### Dados de teste (opcional)

```powershell
python -m flask dados-exemplo              # 40 contratos + 12 meses de índices fictícios
python -m flask limpar-exemplo --indices   # apaga tudo que é de exemplo antes de usar de verdade
```

## Telas

| Tela | O que faz |
|---|---|
| **Painel** | Indicadores (clique num card para ver o detalhamento), listas de tratativas, gráfico de índices, filtros e tabela analítica ordenável. "Exportar Excel" respeita os filtros. |
| **Cadastrar contrato** | Formulário para inserir dados direto no portal. Editar/excluir pelo ✎ na tabela. |
| **Importar planilha** | Carrega um .xlsx. Modo "adicionar" ou "substituir" (substitui só o que veio de planilha). |
| **Índices** | Lançamento mensal de IPCA, IGP-M e IPC/FIPE acumulados em 12 meses. |

## Regras dos indicadores

Cada contrato cai em **uma única** categoria (por isso os cards de tratativa somam o total "Em tratativas"):

| Card | Regra |
|---|---|
| Em dia | Status = **Finalizado** |
| Contratos vencidos | Status = Em Tratativa **e** data Fim já passou |
| Próximos do vencimento | Em Tratativa, não vencido, **Tratativa Vigência = Sim** |
| Próximos do reajuste | Em Tratativa, não vencido, Tratativa Vigência = Não e **Tratativa Reajuste = Sim** |
| Demais em tratativas | Em Tratativa sem nenhuma das marcações acima |

Os selos "vence em Xd" e "reajuste próximo" da tabela usam `DIAS_ALERTA_VENCIMENTO` e `DIAS_ALERTA_REAJUSTE` do `.env`.

## Planilha

A importação lê a aba **Base_Contratos** (contratos) e, se existir, a aba **Base_Indices** (IPCA, IGP-M, IPC/FIPE).
"Valor Mensal" aceita número ou "Variável". O "Exportar Excel" gera o mesmo layout da Base_Contratos, então dá para
editar no Excel e reimportar com o modo "Substituir".

## Onde ajustar

- Opções de status, tipos de contrato → `config.py`
- Nomes de colunas aceitos na planilha → `MAPA_COLUNAS` em `app/services.py`
- Mudou um modelo em `app/models.py`? Rode `python -m flask db migrate -m "descricao"` e `python -m flask db upgrade`.

## Estrutura

```
portal-contratos/
├── run.py · config.py · requirements.txt · .env.example
├── migrations/                 # histórico do banco (Flask-Migrate)
└── app/
    ├── __init__.py             # cria o app
    ├── models.py               # Contrato e Indice
    ├── forms.py                # formulários (aceitam vírgula decimal)
    ├── services.py             # indicadores, importação e exportação
    ├── routes.py               # páginas
    ├── seed.py                 # comandos de dados de exemplo
    ├── utils.py                # datas/valores no padrão BR
    ├── templates/              # HTML
    └── static/                 # CSS, JS e Chart.js local (funciona sem internet)
```
