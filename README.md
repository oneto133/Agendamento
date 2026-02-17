# Sistema de Reservas com Pagamento Pix (Asaas)

Aplicacao web para agendamento de servicos com cobranca via Pix integrada ao Asaas.

## Objetivo

Este projeto foi desenvolvido para:

- permitir que clientes realizem agendamentos de forma simples;
- gerar cobranca Pix automaticamente no Asaas;
- acompanhar o status do pagamento em tempo real;
- concluir o agendamento somente apos confirmacao de pagamento.

## Demonstracao do Fluxo

1. Cliente preenche formulario de agendamento.
2. Sistema valida dados (CPF, data, horario e servico).
3. API cria cliente no Asaas.
4. API cria cobranca Pix no Asaas.
5. Sistema exibe pagina de pagamento com QR Code e codigo Pix copia e cola.
6. Frontend consulta periodicamente o status da cobranca.
7. Quando o pagamento e confirmado, o usuario e redirecionado para a tela de agendamento concluido.

## Stack utilizada

- Backend: FastAPI
- Frontend: HTML + CSS + Jinja2
- Banco de dados: SQLite (`reservas.db`)
- HTTP client: httpx
- Servidor local: Uvicorn
- Gateway de pagamento: Asaas (Sandbox)

## Estrutura do projeto

```text
Reservas/
|- app.py
|- requirements.txt
|- reservas.db
|- templates/
|  |- agendamento.html
|  |- pagamento.html
|  |- agendamento_concluido.html
|- static/
|  |- css/
|     |- agendamento.css
```

## Pre-requisitos

- Python 3.10+
- pip
- Conta no Asaas (ambiente Sandbox)

## Como executar localmente

1. Clone o repositorio e entre na pasta do projeto.
2. (Opcional, recomendado) crie e ative um ambiente virtual.
3. Instale as dependencias:

```bash
pip install -r requirements.txt
```

4. Configure as variaveis de ambiente.
5. Rode a aplicacao:

```bash
uvicorn app:app --reload
```

6. Acesse no navegador:

```text
http://127.0.0.1:8000
```

## Variaveis de ambiente (passo mais importante)

A aplicacao depende de duas variaveis:

- `ASAAS_API_KEY`: token da API do Asaas (Sandbox ou Producao)
- `SESSION_SECRET_KEY`: chave usada na sessao do FastAPI

### PowerShell (Windows)

```powershell
$env:ASAAS_API_KEY='SEU_TOKEN_DO_ASAAS'
$env:SESSION_SECRET_KEY='UMA_CHAVE_FORTE_E_ALEATORIA'
uvicorn app:app --reload
```

### Observacoes importantes

- nunca suba tokens reais para o GitHub;
- use valores de exemplo em documentacao;
- para producao, defina as variaveis no provedor (Render, Railway, VPS etc.), nao no codigo.

## Passo a passo da configuracao da API no Asaas (Sandbox)

1. Acesse sua conta Asaas e entre no ambiente de testes (Sandbox).
2. No painel, abra a area de integracoes/API.
3. Gere um token de API para o ambiente Sandbox.
4. Copie o token e configure na variavel `ASAAS_API_KEY`.
5. Inicie a aplicacao localmente com `uvicorn app:app --reload`.
6. Crie um agendamento no formulario para disparar a criacao de cliente e cobranca.
7. Valide se a cobranca foi criada no painel do Asaas e se o Pix foi retornado na tela de pagamento.

### Endpoints do Asaas usados no projeto

- `POST /customers` para criar o cliente no Asaas
- `POST /payments` para criar cobranca Pix
- `GET /payments/{id}/pixQrCode` para obter QR Code e payload Pix
- `GET /payments/{id}` para consultar status e confirmar pagamento

## Regras de negocio implementadas

- agendamento permitido apenas entre hoje e os proximos 7 dias;
- horarios pre-definidos entre 08:00 e 19:00;
- validacao de CPF (11 digitos);
- duas formas de pagamento:
  - adiantado (valor com desconto, com registro de valor pago no ato);
  - no horario (valor cheio);
- status de pagamento persistido no banco;
- redirecionamento automatico para tela final apos confirmacao.

## Rotas principais

- `GET /` formulario de agendamento
- `POST /` cria reserva e cobranca no Asaas
- `GET /pagamento/{reserva_id}` tela do Pix
- `GET /pagamento-status/{reserva_id}` consulta status da cobranca
- `GET /agendamento-concluido/{reserva_id}` confirmacao final

## Banco de dados

A tabela `reservas` armazena:

- dados do cliente e do agendamento;
- informacoes da cobranca Asaas (`asaas_customer_id`, `asaas_payment_id`, `asaas_invoice_url`);
- payload Pix e QR Code;
- status do pagamento (`PENDING` / `CONFIRMED`);
- timestamps de criacao e confirmacao.

## Seguranca e boas praticas

- nao salvar tokens reais em arquivos versionados;
- usar `SESSION_SECRET_KEY` forte em producao;
- tratar erros de integracao com API externa;
- manter logs e monitoramento de falhas de pagamento.

## Proximos passos tecnicos

- separar configuracoes por ambiente (dev/homolog/producao);
- adicionar testes automatizados para regras de negocio;
- incluir endpoint de webhook do Asaas para confirmacao server-to-server (evita polling).

## Conteudo pronto para LinkedIn

Projeto concluido: Sistema de Reservas com integracao Pix via Asaas.

Destaques da implementacao:

- FastAPI + SQLite para backend leve e rapido;
- integracao completa com API Asaas (criacao de cliente, cobranca e consulta de status);
- fluxo de pagamento Pix com QR Code e copia e cola;
- controle de status de pagamento e liberacao da confirmacao apenas apos pagamento aprovado;
- configuracao de variaveis de ambiente para proteger credenciais.

Aprendizados principais:

- modelagem de fluxo de pagamento assinado por status;
- integracao segura com API de terceiros usando token;
- importancia de separar credenciais do codigo para publicacao e deploy.
