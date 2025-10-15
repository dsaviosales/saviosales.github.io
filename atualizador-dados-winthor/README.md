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

> **Dica rápida**: se preferir automatizar a criação do ambiente virtual, rode `python -m venv .venv && source .venv/bin/activate` (macOS/Linux) ou `python -m venv .venv; .\.venv\Scripts\Activate.ps1` (Windows PowerShell) diretamente do diretório `atualizador-dados-winthor`.

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
   - Flags úteis: `--api-url`, `--max-rps`, `--timeout`, `--retries`, `--dry-run`.
3. Execute a atualização no Oracle:
   ```bash
   python atualizadados.py --csv files/fornecedores.csv
   ```
   - Flags úteis: `--dry-run`, `--limit`, `--select '{"estado": "SP"}'`.

## Testes e validações

Com o ambiente virtual ativo, utilize os comandos abaixo para validar rapidamente o projeto:

- Instale as dependências de testes (se ainda não instaladas):
  ```bash
  pip install -r requirements.txt
  pip install pytest
  ```
- Execute a suíte de testes automatizados (inclui o teste PyTest do mapeamento de CNAE e os doctests do módulo de tratamento de dados):
  ```bash
  pytest -q
  python -m doctest -v utils/tratardados.py
  ```
- Opcional: compile toda a árvore Python para garantir ausência de erros de sintaxe.
  ```bash
  python -m compileall .
  ```

Esses comandos funcionam tanto no Windows (PowerShell) quanto no macOS/Linux (bash/zsh); ajuste o prefixo `python` para `python3` se necessário no seu ambiente.

## Registro e observabilidade

- Logs são gravados em `log/download_info.log` e replicados no console.
- O cache TinyDB fica em `eunix.json` com upsert por CNPJ.

## Troubleshooting

- **Erro `DPI-1047: Cannot locate a 64-bit Oracle Client library`**: confirme que o Oracle Instant Client compatível com seu sistema operacional está instalado, descompactado e referenciado no `PATH` (e `DYLD_LIBRARY_PATH` no macOS). Reinicie o terminal após ajustar as variáveis.
- **Timeouts ou `HTTP 429` ao consultar a API**: reduza o ritmo com `--max-rps`, aumente `--timeout` e `--retries`, ou faça uma pausa antes de retomar a coleta para respeitar o limite do provedor.
- **Falha ao conectar no Oracle**: valide host, porta, usuário e senha no `config/.env`, verifique conectividade de rede/VPN e utilize `python atualizadados.py --dry-run` para garantir que as credenciais estejam corretas antes de aplicar commits.

## Checklist rápido

- [ ] Ambiente virtual criado e dependências instaladas.
- [ ] `config/.env` preenchido com credenciais válidas.
- [ ] CSV de fornecedores revisado.
- [ ] `python buscardados.py` executado com sucesso.
- [ ] `python atualizadados.py` aplicado (ou revisado com `--dry-run`).

## Tarefas VS Code

O arquivo `.vscode/tasks.json` fornece atalhos para executar os dois passos principais direto do editor.

## Interface desktop (PySide6)

- Execute a interface TOTVS-like com o comando abaixo (após ativar o ambiente virtual):
  ```bash
  python -m app_ui.main
  ```
- A janela permite importar CSV, consultar a API e aplicar atualizações usando *workers* que chamam os mesmos serviços Python do CLI.
- Utilize o menu para alternar entre tema claro/escuro e acompanhar os status de API/Oracle.

## Empacotamento com PyInstaller

1. Instale o PyInstaller dentro do ambiente virtual caso ainda não esteja disponível:
   ```bash
   pip install pyinstaller
   ```
2. Gere os executáveis (CLI + UI) usando o script de build:
   - **Windows (PowerShell)**
     ```powershell
     cd atualizador-dados-winthor
     python build.py --onefile
     ```
   - **macOS / Linux (bash/zsh)**
     ```bash
     cd atualizador-dados-winthor
     python3 build.py --onefile
     ```
   - Use `--target` (`buscardados`, `atualizadados`, `atualizador-ui`) para compilar executáveis específicos.
3. Os binários ficarão disponíveis na pasta `atualizador-dados-winthor/dist/`. A pasta `build/` e possíveis arquivos `.spec` são descartáveis e já estão ignorados no Git.
