# Dashboard Gerencial de Metas por Setor

Sistema interno para acompanhamento de metas de vendas por setor, comparando
metas cadastradas com as vendas reais registradas no SQL Server (`sismoura`).

Stack: **Python + Flask** no backend, **HTML5 + CSS3 + JavaScript puro** no
frontend, **SQLite** para configurações locais (setores, grupos, metas) e
**SQL Server** como fonte de dados de vendas. Não depende de internet para
funcionar (Chart.js está vendorizado localmente).

---

## 1. Instalação

### Pré-requisitos

1. **Python 3.11+** instalado e no PATH ([python.org](https://www.python.org/downloads/)).
2. **ODBC Driver 17 (ou 18) para SQL Server** instalado no Windows.
   Baixe em: https://learn.microsoft.com/sql/connect/odbc/download-odbc-driver-for-sql-server
3. Acesso de rede ao servidor SQL Server (`server_pn`, banco `sismoura`).

### Passo a passo

1. Extraia/clone esta pasta em um local de sua preferência.
2. Dê dois cliques em **`scripts\instalar.bat`**. Esse script:
   - cria um ambiente virtual Python em `.venv`;
   - instala as dependências listadas em `requirements.txt`;
   - cria o arquivo `.env` a partir de `.env.example`, se ainda não existir.
3. Abra o arquivo **`.env`** gerado e confirme os dados de conexão do SQL Server
   (veja a seção [Configuração do SQL Server](#3-configuração-do-sql-server)).

---

## 2. Execução

Dê dois cliques em **`scripts\iniciar.bat`**. O script:

1. ativa o ambiente virtual;
2. inicia o servidor Flask na porta configurada em `FLASK_PORT` (padrão `5000`);
3. abre automaticamente o navegador já no endereço correto.

**Se a porta 5000 já estiver ocupada** — por exemplo, outro sistema Flask
rodando na mesma máquina — o sistema detecta isso automaticamente na
inicialização e sobe na próxima porta livre (5001, 5002, ...), sem precisar
configurar nada. O terminal mostra um aviso informando qual porta foi usada,
e o navegador abre nela automaticamente.

Para acessar de outro computador na mesma rede, use `http://<IP-desta-máquina>:<porta>`
(a porta aparece no terminal ao iniciar). Para encerrar, feche a janela do
terminal ou pressione `Ctrl+C`.

---

## 3. Configuração do SQL Server

As credenciais ficam no arquivo `.env` (nunca no código-fonte):

```env
SQL_SERVER=server_pn
SQL_DATABASE=sismoura
SQL_USERNAME=sa
SQL_PASSWORD=SENHA_AQUI
SQL_DRIVER=ODBC Driver 17 for SQL Server

CACHE_TTL_SECONDS=120
FLASK_HOST=0.0.0.0
FLASK_PORT=5000
FLASK_DEBUG=false
```

| Variável | Descrição |
|---|---|
| `SQL_SERVER` | Endereço/nome do servidor SQL Server. |
| `SQL_DATABASE` | Nome do banco de dados (`sismoura`). |
| `SQL_USERNAME` / `SQL_PASSWORD` | Credenciais de acesso. |
| `SQL_DRIVER` | Nome exato do driver ODBC instalado (confira em "Fontes de Dados ODBC"). |
| `CACHE_TTL_SECONDS` | Tempo (segundos) que o dashboard fica em cache antes de recalcular. |
| `FLASK_HOST` / `FLASK_PORT` | Endereço/porta em que o sistema roda. |

Você pode testar a conexão a qualquer momento na tela **Configurações** do
sistema (diagnóstico de SQL Server / SQLite / API), ou via o endpoint
`GET /api/health`.

Se alguma tabela/coluna do SQL Server tiver nome diferente do documentado nas
seções abaixo, ajuste as consultas em `services/vendas_service.py` — são o
único ponto do sistema com SQL bruto contra o banco de vendas.

---

## 4. Estrutura do projeto

```
├── app.py                 # Ponto de entrada: cria o Flask app, registra rotas, logging
├── config.py               # Leitura do .env
├── database/
│   ├── sql_server.py       # Conexão pyodbc + execução de queries parametrizadas
│   ├── sqlite.py            # Conexão SQLite + criação de tabelas
│   └── models.py            # DDL das tabelas de configuração local
├── services/                # Regras de negócio (sem depender de Flask)
│   ├── calculos.py          # Fórmulas de meta/percentual — puras e testadas
│   ├── vendas_service.py    # Consultas agregadas ao SQL Server
│   ├── setores_service.py   # CRUD de setores e associação com grupos
│   ├── metas_service.py     # CRUD de metas + cálculo automático de meta percentual
│   └── dashboard_service.py # Orquestra tudo + cache em memória
├── routes/                  # Blueprints Flask (páginas HTML + API JSON)
├── templates/                # HTML (Jinja2)
├── static/                   # CSS, JS e Chart.js vendorizado
├── data/sistema.db           # Banco SQLite (criado automaticamente)
├── logs/app.log              # Log da aplicação (criado automaticamente)
├── tests/                    # Testes automatizados (pytest)
└── scripts/                  # instalar.bat / iniciar.bat
```

### Como o setor "enxerga" as vendas

O relacionamento setor → grupo de produto é cadastrado no SQLite local
(tabela `setor_grupo`), pois um grupo pode pertencer a mais de um setor.
Para calcular o faturamento de um setor, o sistema busca os códigos de grupo
associados no SQLite e usa esses códigos para filtrar as vendas no SQL Server
— nunca há um JOIN direto entre os dois bancos. No dashboard principal, isso é
feito com uma única consulta agregada cobrindo todos os grupos de uma vez
(não uma consulta por setor), para manter a performance mesmo com um grande
volume de vendas.

---

## 5. Regras de negócio implementadas

- **Meta por valor fixo**: informado diretamente pelo gestor.
- **Meta por percentual**: calculada automaticamente a partir da venda real do
  período-base (mês anterior ou mesmo mês do ano anterior) — o gestor nunca
  digita o valor histórico manualmente.
- **Percentual esperado até hoje**: proporcional ao dia do mês corrente
  (calendário real, considerando anos bissextos); 100% para meses já
  encerrados.
- **Status do setor**: `META BATIDA` (≥100%), `NO RITMO` (realizado ≥
  esperado) ou `ABAIXO DO RITMO`.
- Todos os valores monetários usam `Decimal` para evitar erros de
  arredondamento.

Consulte `services/calculos.py` e `tests/test_calculos.py` para o detalhamento
de cada fórmula.

---

## 6. Testes

```bash
.venv\Scripts\activate
pytest tests/ -v
```

Os testes cobrem as regras de cálculo (dias do mês, ano bissexto, meta fixa e
percentual, percentual esperado/realizado, status), o CRUD de setores/grupos
(incluindo grupo pertencendo a múltiplos setores e deduplicação) e o CRUD de
metas (incluindo o bloqueio de meta percentual sem histórico de vendas).

---

## 7. Solução de problemas

**"Não foi possível conectar ao banco de dados"**: verifique se o servidor
SQL Server está ligado e acessível pela rede, se as credenciais no `.env`
estão corretas e se o driver ODBC informado em `SQL_DRIVER` está instalado.
A tela **Configurações** mostra o diagnóstico detalhado.

**Erros aparecem apenas como mensagem genérica na tela**: o detalhe técnico
fica registrado em `logs/app.log` — nunca é exibido ao usuário final.
