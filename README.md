# Sistema de Reservas com Pagamento Pix (Asaas)

Aplicação web para agendamento de serviços com cobrança via Pix integrada ao Asaas.

## Objetivo

Este projeto foi desenvolvido para:

- permitir que clientes realizem agendamentos de forma simples;
- gerar cobrança Pix automaticamente no Asaas;
- acompanhar o status do pagamento em tempo real;
- concluir o agendamento somente após confirmação de pagamento.

## Demonstração do fluxo

1. Cliente preenche formulário de agendamento.
2. Sistema valida dados (CPF, data, horário e serviço).
3. API cria cliente no Asaas.
4. API cria cobrança Pix no Asaas.
5. Sistema exibe página de pagamento com QR Code e código Pix copia e cola.
6. Frontend consulta periodicamente o status da cobrança.
7. Quando o pagamento é confirmado, o usuário é redirecionado para a tela de agendamento concluído.

## Tecnologias utilizadas

- Backend: FastAPI
- Frontend: HTML + CSS + Jinja2
- Banco de dados: SQLite (`reservas.db`)
- Cliente HTTP: httpx
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

## Pré-requisitos

- Python 3.10+
- pip
- Conta no Asaas (ambiente Sandbox)

## Como executar localmente

1. Clone o repositório e entre na pasta do projeto.
2. (Opcional, recomendado) crie e ative um ambiente virtual.
3. Instale as dependências:

```bash
pip install -r requirements.txt
```

4. Configure as variáveis de ambiente.
5. Rode a aplicação:

```bash
uvicorn app:app --reload
```

6. Acesse no navegador:

```text
http://127.0.0.1:8000
```

## Variáveis de ambiente (passo mais importante)

A aplicação depende de duas variáveis:

- `ASAAS_API_KEY`: token da API do Asaas (Sandbox ou Produção)
- `SESSION_SECRET_KEY`: chave usada na sessão do FastAPI

### PowerShell (Windows)

```powershell
$env:ASAAS_API_KEY='SEU_TOKEN_DO_ASAAS'
$env:SESSION_SECRET_KEY='UMA_CHAVE_FORTE_E_ALEATÓRIA'
uvicorn app:app --reload
```

### Observações importantes

- nunca suba tokens reais para o GitHub;
- use valores de exemplo em documentação;
- para produção, defina as variáveis no provedor (Render, Railway, VPS etc.), não no código.

## Passo a passo da configuração da API no Asaas (Sandbox)

1. Acesse sua conta Asaas e entre no ambiente de testes (Sandbox).
2. No painel, abra a área de integrações/API.
3. Gere um token de API para o ambiente Sandbox.
4. Copie o token e configure na variável `ASAAS_API_KEY`.
5. Inicie a aplicação localmente com `uvicorn app:app --reload`.
6. Crie um agendamento no formulário para disparar a criação de cliente e cobrança.
7. Valide se a cobrança foi criada no painel do Asaas e se o Pix foi retornado na tela de pagamento.

### OBS

Criar umas conta AASAS é gratuíta, não é propaganda, no entanto, foi o melhor aplicativo encontrado que se encaixa nos objetivos do projeto.

### Endpoints do Asaas usados no projeto

- `POST /customers` para criar o cliente no Asaas
- `POST /payments` para criar cobrança Pix
- `GET /payments/{id}/pixQrCode` para obter QR Code e payload Pix
- `GET /payments/{id}` para consultar status e confirmar pagamento

## Regras de negócio implementadas

- agendamento permitido apenas entre hoje e os próximos 7 dias;
- horários predefinidos entre 08:00 e 19:00;
- validação de CPF (11 dígitos);
- duas formas de pagamento:
- adiantado (valor com desconto, com registro de valor pago no ato);
- no horário (valor cheio);
- status de pagamento persistido no banco;
- redirecionamento automático para tela final após confirmação.

## Rotas principais

- `GET /` formulário de agendamento
- `POST /` cria reserva e cobrança no Asaas
- `GET /pagamento/{reserva_id}` tela do Pix
- `GET /pagamento-status/{reserva_id}` consulta status da cobrança
- `GET /agendamento-concluido/{reserva_id}` confirmação final

## Banco de dados

A tabela `reservas` armazena:

- dados do cliente e do agendamento;
- informações da cobrança Asaas (`asaas_customer_id`, `asaas_payment_id`, `asaas_invoice_url`);
- payload Pix e QR Code;
- status do pagamento (`PENDING` / `CONFIRMED`);
- timestamps de criação e confirmação.

## Segurança e boas práticas

- não salvar tokens reais em arquivos versionados;
- usar `SESSION_SECRET_KEY` forte em produção;
- tratar erros de integração com API externa;
- manter logs e monitoramento de falhas de pagamento.

## Próximos passos técnicos

- separar configurações por ambiente (dev/homolog/prod);
- adicionar testes automatizados para regras de negócio;
- incluir endpoint de webhook do Asaas para confirmação server-to-server (evita polling).
