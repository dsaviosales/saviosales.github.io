# Atualizador de Dados WinThor

Pipeline para atualização de dados de fornecedores do WinThor consumindo uma API pública de CNPJ.

## Estrutura

```
atualizador-dados-winthor/
├── atualizadados.py
├── buscardados.py
├── config/
│   └── .env                # não versionado
├── database.py
├── eunix.json              # cache TinyDB (ignorado no git)
├── files/
│   └── fornecedores.csv    # lista de CNPJs (coluna CGC)
├── log/
│   └── download_info.log   # logs em tempo de execução (ignorado)
├── requirements.txt
├── utils/
│   ├── normaliza_dados.py
│   └── tratardados.py
└── .vscode/
    └── tasks.json
```

## Preparação do ambiente

1. Instale o Python 3.10 ou superior.
2. Baixe e configure o [Oracle Instant Client](https://www.oracle.com/database/technologies/instant-client.html) compatível com seu sistema operacional.
   - Windows: extraia o pacote ZIP e adicione a pasta ao `PATH` (Ex.: `C:\instantclient_19_8`).
   - macOS: instale o pacote `.dmg`, mova o conteúdo para `/opt/oracle/instantclient` e exporte `PATH` e `DYLD_LIBRARY_PATH`.
3. Crie e ative um ambiente virtual:
   - **Windows (PowerShell)**
     ```powershell
     python -m venv .venv
     .\.venv\Scripts\Activate.ps1
     ```
   - **macOS / Linux (bash/zsh)**
     ```bash
     python3 -m venv .venv
     source .venv/bin/activate
     ```
4. Instale as dependências no ambiente virtual:
   ```bash
   pip install -r requirements.txt
   ```
5. Copie `config/.env.example` para `config/.env` (crie o arquivo com as variáveis abaixo).

### Variáveis obrigatórias (`config/.env`)

```
ORA_USER=seu_usuario
ORA_PASS=sua_senha
ORA_HOST=host.oracle.local
ORA_PORT=1521
ORA_SID=servicename_ou_sid
```

## Uso

1. Preencha `files/fornecedores.csv` com a coluna `CGC` contendo os CNPJs.
2. Rode a coleta para preencher o cache TinyDB:
   ```bash
   python buscardados.py --csv files/fornecedores.csv
   ```
   - Use `--api-url` para apontar outra API.
   - Use `--dry-run` para simular sem gravar o cache.
3. Execute a atualização no Oracle:
   ```bash
   python atualizadados.py --csv files/fornecedores.csv
   ```
   - Use `--dry-run` para revisar as instruções sem aplicar `commit`.

## Registro e observabilidade

- Logs são gravados em `log/download_info.log` e replicados no console.
- O cache TinyDB fica em `eunix.json` com upsert por CNPJ.

## Checklist rápido

- [ ] Ambiente virtual criado e dependências instaladas.
- [ ] `config/.env` preenchido com credenciais válidas.
- [ ] CSV de fornecedores revisado.
- [ ] `python buscardados.py` executado com sucesso.
- [ ] `python atualizadados.py` aplicado (ou revisado com `--dry-run`).

## Tarefas VS Code

O arquivo `.vscode/tasks.json` fornece atalhos para executar os dois passos principais direto do editor.
