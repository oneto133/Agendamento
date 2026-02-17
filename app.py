from datetime import date, datetime, timedelta
from pathlib import Path
import os
import re
import sqlite3
import httpx
from fastapi import FastAPI, Form, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "reservas.db"

SERVICOS = {
    "Brow lamination": {"valor_reservado": 100.0, "valor_com_desconto": 80.0},
    "Fio a Fio": {"valor_reservado": 50.0, "valor_com_desconto": 40.0},
    "Lash lifting": {"valor_reservado": 50.0, "valor_com_desconto": 40.0}
}
HORARIOS = [
    "08:00",
    "09:00",
    "10:00",
    "11:00",
    "12:00",
    "13:00",
    "14:00",
    "15:00",
    "16:00",
    "17:00",
    "18:00",
    "19:00",
]

ASAAS_BASE_URL = "https://sandbox.asaas.com/api/v3"
ASAAS_API_KEY = os.getenv("ASAAS_API_KEY", "")
DEFAULT_CHARGE_VALUE = 50.0
LOCAL_PADRAO = "Endereco ainda nao definido"
STATUS_PAGAMENTO_PENDENTE = "PENDING"
STATUS_PAGAMENTO_PAGO = "CONFIRMED"
STATUS_ASAAS_PAGO = {"RECEIVED", "CONFIRMED", "RECEIVED_IN_CASH"}

app = FastAPI(title="Reservas")
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SESSION_SECRET_KEY", "troque-esta-chave-em-producao"),
)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _garantir_coluna(conn: sqlite3.Connection, coluna: str, definicao: str) -> None:
    colunas = {row["name"] for row in conn.execute("PRAGMA table_info(reservas)").fetchall()}
    if coluna not in colunas:
        conn.execute(f"ALTER TABLE reservas ADD COLUMN {coluna} {definicao}")


def init_db() -> None:
    with get_db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS reservas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                telefone TEXT NOT NULL,
                cpf TEXT NOT NULL,
                servico TEXT NOT NULL,
                data_reserva TEXT NOT NULL,
                horario TEXT NOT NULL,
                forma_pagamento TEXT NOT NULL,
                valor_total REAL NOT NULL,
                valor_pago_no_ato REAL NOT NULL,
                valor_restante REAL NOT NULL,
                asaas_customer_id TEXT,
                asaas_payment_id TEXT,
                asaas_invoice_url TEXT,
                status_pagamento TEXT NOT NULL DEFAULT 'PENDING',
                pix_payload TEXT,
                pix_qr_base64 TEXT,
                local_atendimento TEXT,
                pago_em TEXT,
                criado_em TEXT NOT NULL
            )
            """
        )

        # Compatibilidade com bancos antigos criados antes dessas colunas.
        _garantir_coluna(conn, "status_pagamento", "TEXT NOT NULL DEFAULT 'PENDING'")
        _garantir_coluna(conn, "pix_payload", "TEXT")
        _garantir_coluna(conn, "pix_qr_base64", "TEXT")
        _garantir_coluna(conn, "local_atendimento", "TEXT")
        _garantir_coluna(conn, "pago_em", "TEXT")


def normalizar_cpf(cpf: str) -> str:
    return re.sub(r"\D", "", cpf)


def cpf_valido(cpf: str) -> bool:
    cpf = normalizar_cpf(cpf)
    return len(cpf) == 11


def asaas_headers() -> dict:
    if not ASAAS_API_KEY:
        raise RuntimeError("ASAAS_API_KEY nao configurada.")

    return {
        "accept": "application/json",
        "content-type": "application/json",
        "access_token": ASAAS_API_KEY,
    }


async def criar_cliente_e_cobranca_asaas(
    nome: str,
    telefone: str,
    cpf: str,
    due_date: str,
) -> dict:
    headers = asaas_headers()

    async with httpx.AsyncClient(timeout=20) as client:
        customer_payload = {
            "name": nome,
            "cpfCnpj": normalizar_cpf(cpf),
            "mobilePhone": re.sub(r"\D", "", telefone),
        }
        customer_response = await client.post(
            f"{ASAAS_BASE_URL}/customers",
            headers=headers,
            json=customer_payload,
        )
        customer_response.raise_for_status()
        customer = customer_response.json()

        payment_payload = {
            "customer": customer["id"],
            "billingType": "PIX",
            "value": DEFAULT_CHARGE_VALUE,
            "dueDate": due_date,
            "description": "Cobranca referente ao agendamento",
        }
        payment_response = await client.post(
            f"{ASAAS_BASE_URL}/payments",
            headers=headers,
            json=payment_payload,
        )
        payment_response.raise_for_status()
        payment = payment_response.json()

        return {
            "customer_id": customer.get("id", ""),
            "payment_id": payment.get("id", ""),
            "invoice_url": payment.get("invoiceUrl", ""),
        }


async def buscar_pix_qrcode_asaas(payment_id: str) -> dict:
    headers = asaas_headers()

    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(
            f"{ASAAS_BASE_URL}/payments/{payment_id}/pixQrCode",
            headers=headers,
        )
        response.raise_for_status()
        data = response.json()
        return {
            "payload": data.get("payload", ""),
            "encoded_image": data.get("encodedImage", ""),
            "expiration_date": data.get("expirationDate", ""),
        }


async def consultar_pagamento_asaas(payment_id: str) -> dict:
    headers = asaas_headers()

    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(
            f"{ASAAS_BASE_URL}/payments/{payment_id}",
            headers=headers,
        )
        response.raise_for_status()
        return response.json()


def registrar_reserva(
    nome: str,
    telefone: str,
    cpf: str,
    servico: str,
    data_reserva: str,
    horario: str,
    forma_pagamento: str,
    valor_total: float,
    valor_pago_no_ato: float,
    valor_restante: float,
    asaas_customer_id: str,
    asaas_payment_id: str,
    asaas_invoice_url: str,
    status_pagamento: str,
    pix_payload: str,
    pix_qr_base64: str,
    local_atendimento: str,
) -> int:
    with get_db() as conn:
        cursor = conn.execute(
            """
            INSERT INTO reservas (
                nome, telefone, cpf, servico, data_reserva, horario,
                forma_pagamento, valor_total, valor_pago_no_ato, valor_restante,
                asaas_customer_id, asaas_payment_id, asaas_invoice_url,
                status_pagamento, pix_payload, pix_qr_base64, local_atendimento,
                criado_em
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                nome,
                telefone,
                normalizar_cpf(cpf),
                servico,
                data_reserva,
                horario,
                forma_pagamento,
                valor_total,
                valor_pago_no_ato,
                valor_restante,
                asaas_customer_id,
                asaas_payment_id,
                asaas_invoice_url,
                status_pagamento,
                pix_payload,
                pix_qr_base64,
                local_atendimento,
                datetime.now().isoformat(timespec="seconds"),
            ),
        )
        return int(cursor.lastrowid)


def buscar_reserva_por_id(reserva_id: int):
    with get_db() as conn:
        return conn.execute("SELECT * FROM reservas WHERE id = ?", (reserva_id,)).fetchone()


def atualizar_status_pagamento(
    reserva_id: int,
    novo_status: str,
    pago_em: str = "",
) -> None:
    with get_db() as conn:
        conn.execute(
            "UPDATE reservas SET status_pagamento = ?, pago_em = COALESCE(NULLIF(?, ''), pago_em) WHERE id = ?",
            (novo_status, pago_em, reserva_id),
        )


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/")
async def agendamento_get(request: Request):
    hoje = date.today()
    limite = hoje + timedelta(days=7)
    servicos_disponiveis = list(SERVICOS.keys())
    servico_padrao = servicos_disponiveis[0]

    dados = request.session.pop(
        "dados",
        {
            "servico": servico_padrao,
            "nome": "",
            "telefone": "",
            "cpf": "",
            "data": "",
            "horario": HORARIOS[0],
            "forma_pagamento": "adiantado",
        },
    )

    erro = request.session.pop("erro", "")
    sucesso = request.session.pop("sucesso", "")

    precos_servico = SERVICOS.get(dados["servico"], SERVICOS[servico_padrao])

    return templates.TemplateResponse(
        "agendamento.html",
        {
            "request": request,
            "servicos": servicos_disponiveis,
            "valor_padrao": precos_servico["valor_reservado"],
            "valor_desconto": precos_servico["valor_com_desconto"],
            "data_min": hoje.isoformat(),
            "data_max": limite.isoformat(),
            "horarios": HORARIOS,
            "dados": dados,
            "erro": erro,
            "sucesso": sucesso,
            "valor_cobranca": f"{DEFAULT_CHARGE_VALUE:.2f}",
        },
    )


@app.post("/")
async def agendamento_post(
    request: Request,
    servico: str = Form(""),
    nome: str = Form(""),
    telefone: str = Form(""),
    cpf: str = Form(""),
    data: str = Form(""),
    horario: str = Form(""),
    forma_pagamento: str = Form("adiantado"),
):
    hoje = date.today()
    limite = hoje + timedelta(days=7)
    servicos_disponiveis = list(SERVICOS.keys())
    servico_padrao = servicos_disponiveis[0]

    dados = {
        "servico": servico.strip() or servico_padrao,
        "nome": nome.strip(),
        "telefone": telefone.strip(),
        "cpf": cpf.strip(),
        "data": data.strip(),
        "horario": horario.strip() or HORARIOS[0],
        "forma_pagamento": forma_pagamento.strip() or "adiantado",
    }

    erro = ""

    if dados["servico"] not in SERVICOS:
        erro = "Servico invalido. Escolha uma opcao da lista."
    elif not dados["nome"] or not dados["telefone"] or not dados["cpf"] or not dados["data"] or not dados["horario"]:
        erro = "Preencha todos os campos obrigatorios."
    elif not cpf_valido(dados["cpf"]):
        erro = "CPF invalido. Informe 11 digitos."
    elif dados["horario"] not in HORARIOS:
        erro = "Horario invalido. Escolha um horario da lista."
    elif dados["forma_pagamento"] not in {"adiantado", "no_horario"}:
        erro = "Forma de pagamento invalida."
    else:
        try:
            data_escolhida = datetime.strptime(dados["data"], "%Y-%m-%d").date()
        except ValueError:
            erro = "Data invalida."
        else:
            if data_escolhida < hoje or data_escolhida > limite:
                erro = (
                    "A reserva deve estar entre hoje e os proximos 7 dias. "
                    f"Periodo permitido: {hoje.isoformat()} ate {limite.isoformat()}."
                )

    if erro:
        request.session["erro"] = erro
        request.session["dados"] = dados
        return RedirectResponse(url="/", status_code=303)

    precos_servico = SERVICOS[dados["servico"]]
    valor_reservado = precos_servico["valor_reservado"]
    valor_com_desconto = precos_servico["valor_com_desconto"]

    if dados["forma_pagamento"] == "adiantado":
        valor_total = valor_com_desconto
        valor_pago_no_ato = valor_com_desconto * 0.5
        valor_restante = valor_total - valor_pago_no_ato
        forma_texto = "Pagamento adiantado"
    else:
        valor_total = valor_reservado
        valor_pago_no_ato = 0.0
        valor_restante = valor_total
        forma_texto = "Pagamento no horario"

    try:
        asaas = await criar_cliente_e_cobranca_asaas(
            nome=dados["nome"],
            telefone=dados["telefone"],
            cpf=dados["cpf"],
            due_date=dados["data"],
        )
    except Exception as exc:
        request.session["erro"] = f"Reserva valida, mas nao foi possivel gerar cobranca no Asaas: {exc}"
        request.session["dados"] = dados
        return RedirectResponse(url="/", status_code=303)

    pix_payload = ""
    pix_qr_base64 = ""
    try:
        pix = await buscar_pix_qrcode_asaas(asaas["payment_id"])
        pix_payload = pix.get("payload", "")
        pix_qr_base64 = pix.get("encoded_image", "")
    except Exception:
        # A cobranca existe mesmo se a consulta do QR falhar; o usuario pode seguir pela fatura.
        pass

    reserva_id = registrar_reserva(
        nome=dados["nome"],
        telefone=dados["telefone"],
        cpf=dados["cpf"],
        servico=dados["servico"],
        data_reserva=dados["data"],
        horario=dados["horario"],
        forma_pagamento=forma_texto,
        valor_total=valor_total,
        valor_pago_no_ato=valor_pago_no_ato,
        valor_restante=valor_restante,
        asaas_customer_id=asaas["customer_id"],
        asaas_payment_id=asaas["payment_id"],
        asaas_invoice_url=asaas["invoice_url"],
        status_pagamento=STATUS_PAGAMENTO_PENDENTE,
        pix_payload=pix_payload,
        pix_qr_base64=pix_qr_base64,
        local_atendimento=LOCAL_PADRAO,
    )

    request.session["dados"] = {
        "servico": servico_padrao,
        "nome": "",
        "telefone": "",
        "cpf": "",
        "data": "",
        "horario": HORARIOS[0],
        "forma_pagamento": "adiantado",
    }

    return RedirectResponse(url=f"/pagamento/{reserva_id}", status_code=303)


@app.get("/pagamento/{reserva_id}")
async def pagamento_get(request: Request, reserva_id: int):
    reserva = buscar_reserva_por_id(reserva_id)
    if not reserva:
        request.session["erro"] = "Reserva nao encontrada."
        return RedirectResponse(url="/", status_code=303)

    if reserva["status_pagamento"] == STATUS_PAGAMENTO_PAGO:
        return RedirectResponse(url=f"/agendamento-concluido/{reserva_id}", status_code=303)

    qr_image = (reserva["pix_qr_base64"] or "").strip()
    if qr_image and not qr_image.startswith("data:image"):
        qr_image = f"data:image/png;base64,{qr_image}"

    return templates.TemplateResponse(
        "pagamento.html",
        {
            "request": request,
            "reserva": reserva,
            "valor_cobranca": f"{DEFAULT_CHARGE_VALUE:.2f}",
            "pix_payload": reserva["pix_payload"] or "",
            "pix_qr_image": qr_image,
            "status_pagamento": reserva["status_pagamento"],
        },
    )


@app.get("/pagamento-status/{reserva_id}")
async def pagamento_status(reserva_id: int):
    reserva = buscar_reserva_por_id(reserva_id)
    if not reserva:
        return JSONResponse(status_code=404, content={"ok": False, "erro": "Reserva nao encontrada."})

    status_local = reserva["status_pagamento"] or STATUS_PAGAMENTO_PENDENTE
    if status_local == STATUS_PAGAMENTO_PAGO:
        return JSONResponse(
            content={
                "ok": True,
                "pago": True,
                "status": status_local,
                "redirect_url": f"/agendamento-concluido/{reserva_id}",
            }
        )

    payment_id = (reserva["asaas_payment_id"] or "").strip()
    if not payment_id:
        return JSONResponse(content={"ok": True, "pago": False, "status": status_local})

    try:
        pagamento = await consultar_pagamento_asaas(payment_id)
    except Exception as exc:
        return JSONResponse(
            status_code=502,
            content={"ok": False, "erro": f"Falha ao consultar Asaas: {exc}"},
        )

    status_asaas = (pagamento.get("status") or "").upper()
    if status_asaas in STATUS_ASAAS_PAGO:
        atualizar_status_pagamento(
            reserva_id=reserva_id,
            novo_status=STATUS_PAGAMENTO_PAGO,
            pago_em=datetime.now().isoformat(timespec="seconds"),
        )
        return JSONResponse(
            content={
                "ok": True,
                "pago": True,
                "status": STATUS_PAGAMENTO_PAGO,
                "redirect_url": f"/agendamento-concluido/{reserva_id}",
            }
        )

    return JSONResponse(content={"ok": True, "pago": False, "status": status_asaas or status_local})


@app.get("/agendamento-concluido/{reserva_id}")
async def agendamento_concluido(request: Request, reserva_id: int):
    reserva = buscar_reserva_por_id(reserva_id)
    if not reserva:
        request.session["erro"] = "Reserva nao encontrada."
        return RedirectResponse(url="/", status_code=303)

    return templates.TemplateResponse(
        "agendamento_concluido.html",
        {
            "request": request,
            "reserva": reserva,
            "valor_cobranca": f"{DEFAULT_CHARGE_VALUE:.2f}",
        },
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
