# Sistema Automatizado de Atualização de Endereços do ERP Winthor

## Visão Geral
Este documento descreve uma solução automatizada para validar e atualizar endereços de clientes no ERP Winthor utilizando os dados oficiais da Receita Federal. O objetivo é garantir que o cadastro esteja sempre coerente com as informações do Cadastro Nacional da Pessoa Jurídica (CNPJ), reduzindo falhas operacionais e melhorando a qualidade dos dados mestre.

## Objetivos Funcionais
1. **Identificação de clientes desatualizados**: selecionar no banco de dados do ERP Winthor os clientes cujo endereço está incompleto, nulo ou marcado para revisão.
2. **Consulta à API da Receita Federal**: enviar o CNPJ de cada cliente selecionado e coletar o endereço oficial retornado pela API.
3. **Normalização e validação**: padronizar o endereço, garantir que todos os campos obrigatórios estejam preenchidos e validar caracteres e tamanhos máximos antes da atualização.
4. **Atualização transacional**: sobrescrever o endereço no ERP apenas quando forem detectadas divergências, garantindo integridade com transações atômicas.
5. **Relatórios e logs**: registrar métricas de execução, atualizações realizadas e falhas identificadas.

## Arquitetura Proposta
- **Agendador**: um job em cron (Linux) ou agendador do orquestrador de tarefas (ex.: Windows Task Scheduler, Airflow) que dispara o processo diariamente, fora do horário de pico.
- **Serviço Orquestrador**: aplicação em Python ou Node.js que coordena cada etapa:
  - Conexão ao banco Winthor via ODBC/SQL.
  - Fila interna de CNPJs a processar (ex.: em memória ou message queue leve).
  - Clientes HTTP resilientes para a API da Receita Federal.
- **Banco de dados Winthor**: fonte oficial dos dados de clientes e destino das atualizações.
- **API Receita Federal (CNPJ)**: provê dados de endereço oficial.
- **Armazenamento de Logs**: arquivos em disco (JSON) ou banco dedicado (ex.: ElasticSearch) para auditoria.

## Fluxo de Processamento
1. **Busca de pendências**
   - Consulta SQL marca clientes com `FLAG_VALIDAR_ENDERECO = 'S'` ou cujos dados obrigatórios (`logradouro`, `numero`, `bairro`, `cidade`, `UF`, `CEP`) estejam vazios.
   - Resultados são carregados em lotes para controlar uso de memória.
2. **Consulta à API**
   - Para cada CNPJ, realizar requisição HTTPS autenticada.
   - Implementar retries exponenciais (ex.: 3 tentativas) e circuit breaker para evitar bloqueios.
3. **Normalização dos dados**
   - Ajustar acentuação, caixa (maiúsculas/minúsculas), remover caracteres especiais indevidos.
   - Aplicar máscaras no CEP (ex.: `NNNNN-NNN`).
   - Mapear campos da API para o padrão Winthor (ex.: `logradouro`, `numero`, `complemento`, `bairro`, `municipio`, `uf`, `cep`).
4. **Comparação e decisão**
   - Comparar cada campo com o valor atual; se houver diferença ou campo vazio, marcar atualização.
   - Registrar motivo da atualização (ex.: "logradouro divergente", "CEP vazio").
5. **Atualização transacional**
   - Executar `BEGIN TRANSACTION` e `UPDATE` parametrizado.
   - Confirmar sucesso com `COMMIT`; em caso de falha, `ROLLBACK` e registrar erro.
6. **Registro de resultados**
   - Atualizar log com métricas (processados, atualizados, erros).
   - Marcar no ERP data/hora da última validação e resetar `FLAG_VALIDAR_ENDERECO`.

## Estratégias de Resiliência
- **Tratamento de erros da API**: capturar códigos HTTP 4xx/5xx e mensagens de erro, registrar no log e pular para o próximo cliente após atingir o limite de tentativas.
- **Timeouts configuráveis**: definir tempo máximo para respostas da API e do banco (ex.: 10s), evitando travamentos.
- **Quarentena de CNPJs problemáticos**: armazenar CNPJs com falhas recorrentes para análise manual.

## Segurança
- Armazenar credenciais da base Winthor e tokens da API em variáveis de ambiente ou serviço de segredos (HashiCorp Vault, AWS Secrets Manager).
- Utilizar HTTPS/TLS para todas as chamadas externas.
- Registrar logs sem expor dados sensíveis (evitar dados completos de endereço nos logs; usar CNPJ mascarado quando necessário).

## Escalabilidade e Performance
- Processar clientes em lotes configuráveis (ex.: 100 registros por lote).
- Implementar pool de conexões com limites de uso para não saturar o ERP.
- Habilitar paralelismo controlado (ex.: workers assíncronos) respeitando limites de requisições da API e capacidade do banco.
- Utilizar caches temporários para respostas recentes, evitando chamadas repetidas para o mesmo CNPJ dentro de curto intervalo.

## Logs e Monitoramento
- **Formato**: JSON estruturado contendo timestamp, CNPJ, status, mensagem e métricas agregadas.
- **Armazenamento**: diretório dedicado (ex.: `/var/log/winthor-enderecos/`) com rotação diária.
- **Notificações**: ao final da execução, enviar resumo por e-mail, Teams ou Slack.
- **Métricas**: quantidade processada, atualizações aplicadas, falhas por tipo, tempo total de execução.

## Considerações Operacionais
- Executar o job fora do horário comercial (ex.: 02:00) para minimizar impacto.
- Manter checklist de pré-requisitos (conectividade, credenciais válidas, espaço em disco).
- Planejar teste inicial em ambiente de homologação com subset de clientes.
- Implementar feature flag para ativar/desativar atualizações automáticas rapidamente.

## Roadmap de Implementação
1. **Preparação**: configurar credenciais seguras, ambiente de desenvolvimento e acesso ao banco Winthor.
2. **Desenvolvimento**: criar scripts de consulta e atualização, clientes HTTP e rotinas de normalização.
3. **Testes**: unitários para normalização/comparação, integração com API mock, testes de carga leves.
4. **Implantação**: configurar agendador, monitoramento e políticas de log.
5. **Operação contínua**: revisar logs diariamente, ajustar lotes e limites conforme performance real.

## Resultado Esperado
Ao final de cada execução, o sistema deve produzir uma mensagem de resumo no formato:

> "Processo de atualização finalizado. 150 clientes processados, 25 endereços atualizados, 3 falhas registradas."

Esse fluxo garante cadastros confiáveis, reduz manutenção manual e mantém o ERP alinhado com as informações oficiais da Receita Federal.

## Implementação de Referência

O script `winthor_address_updater.py` acompanha este documento como um exemplo funcional do orquestrador descrito. Ele utiliza `pyodbc` para se conectar ao banco do Winthor e a API pública de consulta de CNPJ para obter os endereços oficiais. As dependências necessárias estão listadas em `requirements.txt`.

### Execução

1. Configure as variáveis de ambiente `WINTHOR_DSN`, `WINTHOR_DB_USER` e `WINTHOR_DB_PASSWORD` com as credenciais de acesso ao ERP.
2. Instale as dependências com `pip install -r requirements.txt`.
3. Execute `python -m winthor_automation.src.winthor_address_updater --run-once` para processar um lote único ou omita `--run-once` para manter o processo em execução contínua, utilizando o intervalo definido em `--interval-hours` (padrão: 24 horas).

Os logs de execução são gravados no diretório `logs/`, permitindo auditoria completa de cada ciclo do processo.
