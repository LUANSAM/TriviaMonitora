import json
import os
import secrets
import uuid
from datetime import datetime, timezone
from functools import wraps

from dotenv import load_dotenv
from flask import (
    Flask,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
    send_from_directory,
)
from supabase import Client, create_client
from werkzeug.utils import secure_filename
import certifi
import re

load_dotenv()

try:
    CERT_PATH = certifi.where()
    os.environ["SSL_CERT_FILE"] = CERT_PATH
    os.environ["REQUESTS_CA_BUNDLE"] = CERT_PATH
except Exception:
    pass

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://uykchglnflbidcxxgfcq.supabase.co")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InV5a2NoZ2xuZmxiaWRjeHhnZmNxIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjkyMDM0NjQsImV4cCI6MjA4NDc3OTQ2NH0.d1gQsjFgOjWuUUAtL-24inCo9uPhuz8sV-Ny2cWAcgo")
SUPABASE_SERVICE_ROLE = os.getenv("SUPABASE_SERVICE_ROLE")

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", secrets.token_hex(32))
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024  # 25MB uploads
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

# Atualize estas listas para controlar as opções dos dropdowns da tela de cadastro.
REGISTER_COMPANIES = [
    {"id": "trivia_trens", "label": "Trivia Trens"},
    {"id": "tic_trens", "label": "Tic Trens"},
]

REGISTER_AREAS = [
    {"id": "restabelecimento", "label": "Restabelecimento"},
    {"id": "energia", "label": "Energia"},
    {"id": "sinalizacao", "label": "Sinalização"},
    {"id": "telecom", "label": "Telecom"},
    {"id": "engenharia", "label": "Engenharia"},
    {"id": "civil_vp", "label": "Civil/VP"},
    {"id": "oficinas", "label": "Oficinas"},
    {"id": "mro", "label": "MRO"},
]

supabase: Client | None = None
supabase_service: Client | None = None

# Comentado: inicialização lazy dentro de require_supabase()
# if SUPABASE_URL and SUPABASE_ANON_KEY:
#     try:
#         supabase = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
#     except Exception as exc:
#         supabase = None
#         print(f"[WARN] Supabase client init failed: {exc}")

if SUPABASE_URL and SUPABASE_SERVICE_ROLE:
    try:
        supabase_service = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE)
    except Exception:
        supabase_service = None

COMPONENTES = [
    {"id": "bancos", "label": "Bancos"},
    {"id": "carpetes", "label": "Carpetes"},
    {"id": "espelhos", "label": "Espelhos"},
    {"id": "retrovisores", "label": "Retrovisores"},
    {"id": "lanternas", "label": "Lanternas"},
    {"id": "macaco", "label": "Macaco"},
    {"id": "estepe", "label": "Estepe"},
    {"id": "chave_roda", "label": "Chave de Roda"},
    {"id": "triangulo", "label": "Triângulo"},
    {"id": "radio", "label": "Rádio"},
    {"id": "chave_setas", "label": "Chave de Setas"},
    {"id": "pisca_alerta", "label": "Pisca-Alertas"},
    {"id": "cinto", "label": "Cintos de Segurança"},
]

RISCO_PONTOS = [
    {"id": "frente", "label": "Frente"},
    {"id": "traseira", "label": "Traseira"},
    {"id": "lateral_esq", "label": "Lateral Esquerda"},
    {"id": "lateral_dir", "label": "Lateral Direita"},
    {"id": "para_choque", "label": "Para-choques"},
    {"id": "parabrisa", "label": "Para-brisas"},
    {"id": "retrovisores", "label": "Retrovisores"},
    {"id": "vidros", "label": "Vidros"},
    {"id": "pneus", "label": "Pneus"},
    {"id": "lanternas", "label": "Lanternas"},
]

# Opções para os dropdowns de cadastro de veículos
VEICULO_TIPOS = [
    {"id": "automovel", "label": "Automóvel"},
    {"id": "caminhonete", "label": "Caminhonete"},
    {"id": "suv", "label": "SUV"},
    {"id": "van", "label": "Van"},
    {"id": "caminhao", "label": "Caminhão"},
    {"id": "onibus", "label": "Ônibus"},
    {"id": "moto", "label": "Moto"},
]

VEICULO_COMBUSTIVEIS = [
    {"id": "gasolina", "label": "Gasolina"},
    {"id": "etanol", "label": "Etanol"},
    {"id": "flex", "label": "Flex"},
    {"id": "diesel", "label": "Diesel"},
    {"id": "eletrico", "label": "Elétrico"},
    {"id": "hibrido", "label": "Híbrido"},
    {"id": "gnv", "label": "GNV"},
]

VEICULO_MARCAS = [
    {
        "id": "vw",
        "label": "Volkswagen",
        "models": [
            {"id": "gol", "label": "Gol", "tipo_id": "automovel"},
            {"id": "virtus", "label": "Virtus", "tipo_id": "automovel"},
            {"id": "saveiro", "label": "Saveiro", "tipo_id": "caminhonete"},
            {"id": "polo", "label": "Polo", "tipo_id": "automovel"},
        ],
    },
    {
        "id": "ford",
        "label": "Ford",
        "models": [
            {"id": "ranger", "label": "Ranger", "tipo_id": "caminhonete"},
            {"id": "transit", "label": "Transit", "tipo_id": "van"},
            {"id": "territory", "label": "Territory", "tipo_id": "suv"},
            {"id": "ka", "label": "Ka", "tipo_id": "automovel"},
            {"id": "ka_plus", "label": "Ka Plus", "tipo_id": "automovel"},
        ],
    },
    {
        "id": "toyota",
        "label": "Toyota",
        "models": [
            {"id": "corolla", "label": "Corolla", "tipo_id": "automovel"},
            {"id": "corolla-cross", "label": "Corolla Cross", "tipo_id": "suv"},
            {"id": "hilux", "label": "Hilux", "tipo_id": "caminhonete"},
        ],
    },
    {
        "id": "honda",
        "label": "Honda",
        "models": [
            {"id": "civic", "label": "Civic", "tipo_id": "automovel"},
            {"id": "city", "label": "City", "tipo_id": "automovel"},
            {"id": "hrv", "label": "HR-V", "tipo_id": "suv"},
        ],
    },
    {
        "id": "hyundai",
        "label": "Hyundai",
        "models": [
            {"id": "hb20", "label": "HB20", "tipo_id": "automovel"},
            {"id": "hb20s", "label": "HB20S", "tipo_id": "automovel"},
            {"id": "creta", "label": "Creta", "tipo_id": "suv"},
        ],
    },
    {
        "id": "fiat",
        "label": "Fiat",
        "models": [
            {"id": "strada", "label": "Strada", "tipo_id": "caminhonete"},
            {"id": "toro", "label": "Toro", "tipo_id": "caminhonete"},
            {"id": "cronos", "label": "Cronos", "tipo_id": "automovel"},
        ],
    },
]

FUEL_LEVELS = ["vazio", "1/4", "1/2", "3/4", "cheio"]


def require_supabase() -> Client:
    global supabase
    if supabase is None:
        # Tenta criar o cliente na primeira chamada usando as variáveis de ambiente.
        if SUPABASE_URL and SUPABASE_ANON_KEY:
            try:
                supabase = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
            except Exception as exc:
                raise RuntimeError(
                    "Supabase client not configured. Falha ao inicializar o cliente Supabase: %s" % exc
                ) from exc
        else:
            raise RuntimeError(
                "Supabase client not configured. Defina SUPABASE_ANON_KEY em um .env ou variável de ambiente."
            )
    return supabase


def refresh_session_role() -> None:
    user = session.get("user")
    if not user:
        return
    try:
        client = require_supabase()
        profile = (
            client.table("usuarios")
            .select("nome, empresa, role, autorizado")
            .eq("id", user["id"])
            .single()
            .execute()
        )
        data = profile.data or {}
        resolved_role = data.get("role") or ("admin" if data.get("autorizado") else "user")
        if resolved_role != user.get("role"):
            session["user"]["role"] = resolved_role
        if data.get("nome") and data.get("nome") != user.get("nome"):
            session["user"]["nome"] = data["nome"]
        if data.get("empresa") and data.get("empresa") != user.get("empresa"):
            session["user"]["empresa"] = data.get("empresa")
        if data.get("area") and data.get("area") != user.get("area"):
            session["user"]["area"] = data.get("area")
    except Exception:
        # Se não conseguir atualizar, mantém o valor atual em sessão.
        pass


def login_required(role: str | None = None):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            user = session.get("user")
            if not user:
                flash("Faça login para continuar.", "error")
                return redirect(url_for("login"))
            refresh_session_role()
            if role and user.get("role") != role:
                if user.get("role") != "admin":
                    flash("Acesso não autorizado para este perfil.", "error")
                    return redirect(url_for("dashboard"))
            return func(*args, **kwargs)

        return wrapper

    return decorator


@app.context_processor
def inject_user():
    return {"current_user": session.get("user")}


# Evita que formulários fiquem em cache e reabram ao voltar no navegador
@app.after_request
def add_no_cache_headers(response):
    no_cache_endpoints = {
        "registrar_abastecimento",
        "novo_relatorio",
        "finalizar_relatorio",
        "registrar_avaria",
        "register",
        "login",
    }
    if request.endpoint in no_cache_endpoints:
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


@app.route("/assets/<path:filename>")
def serve_public_asset(filename: str):
    return send_from_directory("assets", filename)


@app.route("/")
def home():
    if session.get("user"):
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user"):
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not email or not password:
            flash("Informe e-mail e senha.", "error")
            return redirect(url_for("login"))

        client = require_supabase()
        try:
            auth_response = client.auth.sign_in_with_password({"email": email, "password": password})
            user = auth_response.user
            profile = (
                client.table("usuarios")
                .select("id, nome, empresa, area, autorizado, role")
                .eq("id", user.id)
                .single()
                .execute()
            )
            profile_data = profile.data if profile.data else {}
        except Exception as exc:  # pragma: no cover - depends on backend response
            flash(f"Não foi possível autenticar: {exc}", "error")
            return redirect(url_for("login"))

        role = profile_data.get("role") or ("admin" if profile_data.get("autorizado") else "user")
        session["user"] = {
            "id": user.id,
            "email": user.email,
            "nome": profile_data.get("nome") or (user.email.split("@")[0] if user.email else "Usuário"),
            "empresa": profile_data.get("empresa"),
            "area": profile_data.get("area"),
            "role": role,
        }
        flash("Bem-vindo!", "success")
        return redirect(url_for("dashboard"))

    return render_template("login.html", active_tab="login")


@app.route("/register", methods=["GET", "POST"])
def register():
    if session.get("user"):
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        empresa = request.form.get("empresa", "").strip()
        area = request.form.get("area", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("password_confirm", "")

        if not nome or not email or not password:
            flash("Informe nome, e-mail e senha.", "error")
            return redirect(url_for("register"))

        if password != confirm:
            flash("As senhas não conferem.", "error")
            return redirect(url_for("register"))

        client = require_supabase()
        try:
            signup_response = client.auth.sign_up({"email": email, "password": password})
            user = signup_response.user
            if not user:
                flash("Não foi possível criar o usuário no Supabase.", "error")
                return redirect(url_for("register"))

            # Se houver service role, confirma o e-mail automaticamente para evitar o erro "email not confirmed".
            if supabase_service:
                try:
                    supabase_service.auth.admin.update_user_by_id(user.id, {"email_confirm": True})
                except Exception:
                    # Se falhar, seguimos, mas o usuário pode precisar confirmar por e-mail.
                    pass

            client.table("usuarios").upsert(
                {
                    "id": user.id,
                    "nome": nome,
                    "email": email,
                    "empresa": empresa or None,
                    "area": area or None,
                    "autorizado": True,
                    "role": "user",
                }
            ).execute()
        except Exception as exc:  # pragma: no cover - depende do backend
            flash(f"Erro ao cadastrar: {exc}", "error")
            return redirect(url_for("register"))

        # Autentica automaticamente e envia para o dashboard do usuário
        session["user"] = {
            "id": user.id,
            "email": email,
            "nome": nome,
            "empresa": empresa or None,
            "area": area or None,
            "role": "user",
        }
        flash("Cadastro realizado! Bem-vindo.", "success")
        return redirect(url_for("dashboard"))

    return render_template(
        "register.html",
        empresas=REGISTER_COMPANIES,
        areas=REGISTER_AREAS,
        active_tab="register",
    )


@app.route("/logout")
def logout():
    """Logout do usuário - revoga autenticação no Supabase e limpa sessão local"""
    user = session.get("user")
    
    # Tentar revogar a autenticação no Supabase
    if user:
        try:
            client = require_supabase()
            if client and hasattr(client, 'auth'):
                client.auth.sign_out()
        except Exception as exc:
            # Se falhar a revogação no Supabase, continua com logout local
            print(f"[WARN] Logout Supabase falhou: {exc}")
    
    # Limpar a sessão local completamente
    session.clear()
    
    flash("Sessão encerrada com sucesso. Até logo!", "success")
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required()
def dashboard():
    user = session.get("user")
    client = require_supabase()
    if user.get("role") == "admin":
        stats = load_admin_stats()
        viagens_abertas = load_open_viagens(client)
        open_trip = get_open_trip_for_user(client, user["id"])
        return render_template("dashboard_admin.html", stats=stats, viagens_abertas=viagens_abertas, open_trip=open_trip)
    open_trip = get_open_trip_for_user(client, user["id"])
    vehicle = fetch_vehicle_details(client, open_trip.get("veiculo_id")) if open_trip else None
    return render_template("dashboard_user.html", open_trip=open_trip, open_trip_vehicle=vehicle)


def load_admin_stats() -> dict:
    client = require_supabase()
    stats = {"usuarios": 0, "relatorios": 0, "avarias": 0, "veiculos": 0, "abastecimentos": 0}
    try:
        stats["usuarios"] = client.table("usuarios").select("id", count="exact").execute().count or 0
        stats["relatorios"] = client.table("relatorios").select("id", count="exact").execute().count or 0
        stats["avarias"] = client.table("avaria").select("id", count="exact").execute().count or 0
        stats["veiculos"] = client.table("veiculo").select("id", count="exact").execute().count or 0
        stats["abastecimentos"] = client.table("abastecimentos").select("id", count="exact").execute().count or 0
    except Exception:
        pass
    return stats


def load_open_viagens(client: Client) -> list[dict]:
    try:
        open_data = (
            client.table("relatorios")
            .select("id, partida_at, relatorio_partida")
            .eq("viagem_aberta", True)
            .order("partida_at")
            .execute()
            .data
            or []
        )
    except Exception:
        return []

    # Extract veiculo_id from JSON payload
    for item in open_data:
        partida_json = item.get("relatorio_partida") or {}
        if isinstance(partida_json, dict):
            item["veiculo_id"] = partida_json.get("veiculo_id")
            condutor = partida_json.get("condutor") or {}
            item["user_id"] = condutor.get("user_id")
            item["nome"] = condutor.get("nome")

    veiculo_ids = list({item["veiculo_id"] for item in open_data if item.get("veiculo_id")})
    vehicles_lookup: dict[str, dict] = {}
    if veiculo_ids:
        try:
            vehicles_response = (
                client.table("veiculo")
                .select("id, placa, modelo, marca, tipo, combustivel")
                .in_("id", veiculo_ids)
                .execute()
                .data
                or []
            )
            vehicles_lookup = {entry["id"]: entry for entry in vehicles_response}
        except Exception:
            vehicles_lookup = {}

    for item in open_data:
        partida_block = item.get("relatorio_partida") or {}
        cab = (partida_block.get("cabecalho") or {}) if isinstance(partida_block, dict) else {}
        combustivel_saida = None
        if isinstance(partida_block, dict):
            combustivel_saida = (partida_block.get("combustivel") or {}).get("saida")
        item["veiculo"] = vehicles_lookup.get(item.get("veiculo_id"))
        item["saida_info"] = {
            "data": cab.get("data_saida"),
            "hora": cab.get("hora_saida"),
            "km_inicial": cab.get("km_inicial"),
            "combustivel": combustivel_saida,
            "modelo": cab.get("modelo"),
            "placa": cab.get("placa"),
        }
    return open_data


@app.route("/relatorios/novo", methods=["GET", "POST"])
@login_required()
def novo_relatorio():
    client = require_supabase()
    user = session.get("user")
    # Filtrar veículos por empresa e area do usuário
    query = client.table("veiculo").select("id, placa, modelo, marca, tipo, combustivel, circulando")
    
    if user.get("empresa"):
        query = query.eq("empresa", user["empresa"])
    if user.get("area"):
        query = query.eq("area", user["area"])
    
    vehicles = (
        query
        .order("modelo")
        .execute()
        .data
        or []
    )
    open_trip = get_open_trip_for_user(client, user["id"])
    if open_trip and request.method == "GET":
        flash("Você já possui uma viagem em andamento. Finalize antes de iniciar uma nova.", "info")
        return redirect(url_for("finalizar_relatorio"))

    if request.method == "POST":
        try:
            if open_trip:
                raise ValueError("Finalize a viagem em andamento antes de iniciar outra.")
            partida_payload = build_partida_payload(vehicles)
            veiculo_id = partida_payload.get("veiculo_id")
            ensure_vehicle_available(client, veiculo_id)
            response = (
                client.table("relatorios")
                .insert(
                    {
                        "userID": user["id"],
                        "veiculoID": veiculo_id,
                        "relatorio_partida": partida_payload,
                        "viagem_aberta": True,
                        "partida_at": datetime.now(timezone.utc).isoformat(),
                    }
                )
                .execute()
            )
            relatorio_id = response.data[0]["id"] if response.data else None
            # Avarias agora são registradas separadamente via dashboard
            # process_avarias(client, partida_payload, relatorio_id, stage="partida", veiculo_id=veiculo_id)
            if veiculo_id:
                client.table("veiculo").update({"circulando": True}).eq("id", veiculo_id).execute()
            flash("Viagem iniciada e checklist salvo!", "success")
            return redirect(url_for("dashboard"))
        except ValueError as exc:
            print(f"[ValueError] {exc}", flush=True)
            flash(str(exc), "error")
        except Exception as exc:  # pragma: no cover - remote API
            print(f"[Exception] {type(exc).__name__}: {exc}", flush=True)
            flash(f"Erro ao salvar relatório: {exc}", "error")

    return render_template(
        "relatorio_form.html",
        componentes=COMPONENTES,
        risco_pontos=RISCO_PONTOS,
        fuel_levels=FUEL_LEVELS,
        veiculos=vehicles,
    )


@app.route("/relatorios/finalizar", methods=["GET", "POST"])
@app.route("/relatorios/finalizar/<string:relatorio_id>", methods=["GET", "POST"])
@login_required()
def finalizar_relatorio(relatorio_id: str | None = None):
    client = require_supabase()
    user = session.get("user")
    record = None
    if relatorio_id:
        try:
            data = (
                client.table("relatorios")
                .select("id, relatorio_partida, viagem_aberta")
                .eq("id", relatorio_id)
                .limit(1)
                .execute()
                .data
                or []
            )
            if data:
                record = data[0]
                partida = record.get("relatorio_partida") or {}
                if isinstance(partida, dict):
                    record["veiculo_id"] = partida.get("veiculo_id")
                    condutor = partida.get("condutor") or {}
                    record["user_id"] = condutor.get("user_id")
            else:
                record = None
        except Exception:
            record = None
    if record is None:
        record = get_open_trip_for_user(client, user["id"])

    if not record or not record.get("viagem_aberta"):
        flash("Nenhuma viagem aberta para finalizar.", "info")
        return redirect(url_for("dashboard"))

    if user.get("role") != "admin" and record.get("user_id") != user["id"]:
        flash("Você não pode finalizar viagens abertas por outros usuários.", "error")
        return redirect(url_for("dashboard"))

    partida_payload = record.get("relatorio_partida") or {}
    
    # Extract veiculo_id from partida_payload if not in record
    if not record.get("veiculo_id") and isinstance(partida_payload, dict):
        record["veiculo_id"] = partida_payload.get("veiculo_id")
    
    print(f"[Finalizar] record veiculo_id: {record.get('veiculo_id')}", flush=True)
    print(f"[Finalizar] partida_payload veiculo_id: {partida_payload.get('veiculo_id') if isinstance(partida_payload, dict) else 'N/A'}", flush=True)
    
    vehicle = fetch_vehicle_details(client, record.get("veiculo_id"))

    if request.method == "POST":
        try:
            entrega_payload = build_entrega_payload(partida_payload if isinstance(partida_payload, dict) else None)
            update_payload = {
                "relatorio_entrega": entrega_payload,
                "viagem_aberta": False,
                "entrega_at": datetime.now(timezone.utc).isoformat(),
            }
            client.table("relatorios").update(update_payload).eq("id", record["id"]).execute()
            # Avarias agora são registradas separadamente via dashboard
            # process_avarias(
            #     client,
            #     entrega_payload,
            #     record["id"],
            #     stage="entrega",
            #     veiculo_id=record.get("veiculo_id"),
            # )
            if record.get("veiculo_id"):
                client.table("veiculo").update({"circulando": False}).eq("id", record["veiculo_id"]).execute()
            flash("Viagem finalizada e relatório salvo!", "success")
            return redirect(url_for("dashboard"))
        except ValueError as exc:
            flash(str(exc), "error")
        except Exception as exc:  # pragma: no cover
            flash(f"Erro ao finalizar a viagem: {exc}", "error")

    cabecalho_partida = (partida_payload.get("cabecalho") or {}) if isinstance(partida_payload, dict) else {}
    return render_template(
        "relatorio_finalizar.html",
        relatorio=record,
        cabecalho_partida=cabecalho_partida,
        veiculo=vehicle,
        fuel_levels=FUEL_LEVELS,
        componentes=COMPONENTES,
        risco_pontos=RISCO_PONTOS,
    )


def build_partida_payload(vehicles: list[dict]) -> dict:
    form = request.form
    print(f"[Form] Chaves recebidas: {list(form.keys())}", flush=True)
    veiculo_id = form.get("veiculo_id") or None
    print(f"[Form] veiculo_id: {veiculo_id}", flush=True)
    vehicle_lookup = {v["id"]: v for v in vehicles}
    veiculo_info = vehicle_lookup.get(veiculo_id) if veiculo_id else {}

    data_hora_saida_raw = form.get("data_hora_saida")
    print(f"[Form] data_hora_saida_raw: {data_hora_saida_raw}", flush=True)
    data_saida = None
    hora_saida = None
    if data_hora_saida_raw:
        try:
            dt_saida = datetime.fromisoformat(data_hora_saida_raw)
            data_saida = dt_saida.strftime("%Y-%m-%d")
            hora_saida = dt_saida.strftime("%H:%M")
        except ValueError:
            raise ValueError("Data e horário de saída inválidos. Use o formato dd/mm/yyyy - HH:mm.")

    cabecalho = {
        "modelo": form.get("modelo", (veiculo_info or {}).get("modelo")),
        "placa": form.get("placa", (veiculo_info or {}).get("placa")),
        "marca": form.get("marca", (veiculo_info or {}).get("marca")),
        "tipo": form.get("tipo", (veiculo_info or {}).get("tipo")),
        "data_saida": data_saida,
        "hora_saida": hora_saida,
        "km_inicial": form.get("km_inicial"),
        "trajeto": form.get("trajeto"),
    }

    print(f"[Form] Cabeçalho: modelo={cabecalho['modelo']}, placa={cabecalho['placa']}, km={cabecalho['km_inicial']}", flush=True)

    if not cabecalho["modelo"] or not cabecalho["placa"]:
        raise ValueError("Informe o modelo e a placa do veículo.")
    if not cabecalho["data_saida"] or not cabecalho["hora_saida"]:
        raise ValueError("Informe data e horário de saída.")
    if not cabecalho["km_inicial"]:
        raise ValueError("Informe o KM inicial.")

    componentes_data = []
    for item in COMPONENTES:
        componentes_data.append(
            {
                "nome": item["label"],
                "status": form.get(f"component_status_{item['id']}", "C"),
                "observacao": form.get(f"component_obs_{item['id']}", ""),
            }
        )

    riscos_data = []
    for ponto in RISCO_PONTOS:
        riscos_data.append(
            {
                "ponto": ponto["label"],
                "status": form.get(f"risco_status_{ponto['id']}", "C"),
                "observacao": form.get(f"risco_obs_{ponto['id']}", ""),
            }
        )

    combustivel = {
        "saida": form.get("combustivel_saida"),
        "chegada": None,
    }

    print(f"[Form] Combustível saída: {combustivel['saida']}", flush=True)

    if not combustivel["saida"]:
        raise ValueError("Informe o nível de combustível na saída.")

    current_user = session.get("user") or {}
    condutor = {
        "nome": current_user.get("nome"),
        "user_id": current_user.get("id"),
    }

    avaria_descricoes = form.getlist("avaria_descricao[]")
    avaria_locais = form.getlist("avaria_local[]")
    avaria_entries = []
    for idx, descricao in enumerate(avaria_descricoes):
        descricao = (descricao or "").strip()
        local = avaria_locais[idx] if idx < len(avaria_locais) else ""
        if descricao:
            avaria_entries.append({"descricao": descricao, "local": local})

    relatorio = {
        "veiculo_id": veiculo_id,
        "cabecalho": cabecalho,
        "componentes": componentes_data,
        "riscos": riscos_data,
        "combustivel": combustivel,
        "condutor": condutor,
        "avarias": avaria_entries,
        "assinatura": {"condutor": form.get("assinatura_condutor")},
    }
    return relatorio


def build_entrega_payload(partida_payload: dict | None = None) -> dict:
    form = request.form
    print(f"[Entrega] Chaves do form: {list(form.keys())}", flush=True)
    print(f"[Entrega] partida_payload recebido: {partida_payload is not None}", flush=True)
    if partida_payload:
        print(f"[Entrega] veiculo_id no partida_payload: {partida_payload.get('veiculo_id')}", flush=True)
    
    # Parse datetime-local input
    data_hora_chegada_raw = form.get("data_hora_chegada")
    print(f"[Entrega] data_hora_chegada_raw: {data_hora_chegada_raw}", flush=True)
    data_chegada = None
    hora_chegada = None
    if data_hora_chegada_raw:
        try:
            dt_chegada = datetime.fromisoformat(data_hora_chegada_raw)
            data_chegada = dt_chegada.strftime("%Y-%m-%d")
            hora_chegada = dt_chegada.strftime("%H:%M")
        except ValueError:
            raise ValueError("Data e horário de chegada inválidos. Use o formato dd/mm/yyyy - HH:mm.")
    
    km_final = form.get("km_final")
    combustivel_chegada = form.get("combustivel_chegada")

    if not data_chegada or not hora_chegada:
        raise ValueError("Informe data e horário da chegada.")
    if not km_final:
        raise ValueError("Informe o KM final.")

    try:
        km_final_int = int(km_final)
    except ValueError as exc:
        raise ValueError("KM final inválido.") from exc

    km_inicial_val = None
    if partida_payload:
        try:
            km_inicial_val = int((partida_payload.get("cabecalho") or {}).get("km_inicial") or 0)
        except (TypeError, ValueError):
            km_inicial_val = None
    if km_inicial_val is not None and km_final_int < km_inicial_val:
        raise ValueError("KM final deve ser maior ou igual ao KM inicial.")

    # Build cabecalho
    cabecalho = {
        "data_chegada": data_chegada,
        "hora_chegada": hora_chegada,
        "km_final": km_final_int,
        "trajeto": form.get("trajeto"),
    }

    # Process componentes
    componentes_data = []
    for item in COMPONENTES:
        componentes_data.append(
            {
                "nome": item["label"],
                "status": form.get(f"component_status_{item['id']}", "C"),
                "observacao": form.get(f"component_obs_{item['id']}", ""),
            }
        )

    # Process riscos
    riscos_data = []
    for ponto in RISCO_PONTOS:
        riscos_data.append(
            {
                "ponto": ponto["label"],
                "status": form.get(f"risco_status_{ponto['id']}", "C"),
                "observacao": form.get(f"risco_obs_{ponto['id']}", ""),
            }
        )

    # Combustivel
    combustivel = {
        "saida": None,
        "chegada": combustivel_chegada,
    }

    # Avarias
    avaria_descricoes = form.getlist("avaria_descricao[]")
    avaria_locais = form.getlist("avaria_local[]")
    avaria_entries = []
    for idx, descricao in enumerate(avaria_descricoes):
        descricao = (descricao or "").strip()
        local = avaria_locais[idx] if idx < len(avaria_locais) else ""
        if descricao:
            avaria_entries.append({"descricao": descricao, "local": local})

    payload = {
        "cabecalho": cabecalho,
        "componentes": componentes_data,
        "riscos": riscos_data,
        "combustivel": combustivel,
        "avarias": avaria_entries,
    }
    print("[Entrega] Payload criado com sucesso", flush=True)
    return payload


def ensure_vehicle_available(client: Client, veiculo_id: str | None) -> None:
    if not veiculo_id:
        return
    try:
        # Check all open trips and extract veiculo_id from JSON
        open_trips = (
            client.table("relatorios")
            .select("id, relatorio_partida")
            .eq("viagem_aberta", True)
            .execute()
            .data
            or []
        )
        for trip in open_trips:
            partida = trip.get("relatorio_partida") or {}
            if isinstance(partida, dict) and partida.get("veiculo_id") == veiculo_id:
                raise ValueError("Este veículo já está com uma viagem aberta.")
    except ValueError:
        raise
    except Exception:
        pass


def get_open_trip_for_user(client: Client, user_id: str) -> dict | None:
    try:
        data = (
            client.table("relatorios")
            .select("id, partida_at, relatorio_partida, viagem_aberta")
            .eq("viagem_aberta", True)
            .order("partida_at", desc=True)
            .execute()
            .data
            or []
        )
        # Filter by user_id from JSON
        for item in data:
            partida = item.get("relatorio_partida") or {}
            if isinstance(partida, dict):
                condutor = partida.get("condutor") or {}
                if condutor.get("user_id") == user_id:
                    item["veiculo_id"] = partida.get("veiculo_id")
                    item["user_id"] = user_id
                    item["nome"] = condutor.get("nome")
                    return item
    except Exception:
        return None
    return None


def fetch_vehicle_details(client: Client, veiculo_id: str | None) -> dict | None:
    if not veiculo_id:
        return None
    try:
        response = (
            client.table("veiculo")
            .select("id, placa, modelo, marca, tipo, combustivel, circulando")
            .eq("id", veiculo_id)
            .single()
            .execute()
        )
        return response.data if response.data else None
    except Exception:
        return None


def process_avarias(
    client: Client,
    relatorio_payload: dict,
    relatorio_id: str | None,
    stage: str = "partida",
    veiculo_id: str | None = None,
) -> None:
    descricao_list = request.form.getlist("avaria_descricao[]")
    local_list = request.form.getlist("avaria_local[]")
    fotos = request.files.getlist("avaria_foto[]")

    stage_slug = stage or "partida"
    prefix_base = veiculo_id or relatorio_payload.get("veiculo_id") or "sem-veiculo"

    for idx, descricao in enumerate(descricao_list):
        descricao = descricao.strip()
        foto = fotos[idx] if idx < len(fotos) else None
        local = local_list[idx] if idx < len(local_list) else None
        if not descricao and (not foto or not foto.filename):
            continue
        foto_url = None
        if foto and foto.filename:
            foto_url = upload_image(
                bucket="avarias",
                file_storage=foto,
                prefix=f"{prefix_base}/{relatorio_id or uuid.uuid4()}/{stage_slug}",
            )
        client.table("avaria").insert(
            {
                "veiculoID": veiculo_id or relatorio_payload.get("veiculo_id"),
                "userID": session["user"]["id"],
                "descricao": descricao or local,
                "foto": foto_url,
            }
        ).execute()


def upload_image(bucket: str, file_storage, prefix: str) -> str | None:
    if not file_storage or not file_storage.filename:
        return None
    filename = secure_filename(file_storage.filename)
    _, ext = os.path.splitext(filename)
    ext = ext.lower() or ".jpg"
    new_name = f"{prefix}/{uuid.uuid4().hex}{ext}"
    data = file_storage.read()
    file_storage.seek(0)
    storage = require_supabase().storage.from_(bucket)
    # Supabase storage upload espera headers com strings; bool em headers causa erro em httpx.
    storage.upload(
        new_name,
        data,
        {
            "content-type": file_storage.mimetype or "image/jpeg",
            # use string para evitar AttributeError em httpx (bool não tem encode)
            "upsert": "false",
        },
    )
    public_url = storage.get_public_url(new_name)
    return public_url


@app.route("/admin/relatorios")
@login_required("admin")
def historico_relatorios():
    client = require_supabase()
    user = session.get("user") or {}
    data = (
        client.table("relatorios")
        .select(
            "id, created_at, relatorio_partida, relatorio_entrega, viagem_aberta, partida_at, entrega_at"
        )
        .order("created_at", desc=True)
        .limit(200)
        .execute()
        .data
        or []
    )

    # Extract veiculo_id and user info from JSON
    for item in data:
        partida_json = item.get("relatorio_partida") or {}
        if isinstance(partida_json, dict):
            item["veiculo_id"] = partida_json.get("veiculo_id")
            condutor = partida_json.get("condutor") or {}
            item["nome"] = condutor.get("nome")

    veiculo_ids = list({item["veiculo_id"] for item in data if item.get("veiculo_id")})
    vehicles_lookup: dict[str, dict] = {}
    if veiculo_ids:
        try:
            vehicles_response = (
                client.table("veiculo")
                .select("id, placa, modelo, marca, empresa, area")
                .in_("id", veiculo_ids)
                .execute()
                .data
                or []
            )
            vehicles_lookup = {entry["id"]: entry for entry in vehicles_response}
        except Exception:
            vehicles_lookup = {}

    filtered_data = []
    for item in data:
        partida_json = item.get("relatorio_partida") or {}
        entrega_json = item.get("relatorio_entrega") or {}
        cab_partida = (partida_json.get("cabecalho") or {}) if isinstance(partida_json, dict) else {}
        cab_entrega = (entrega_json.get("cabecalho") or {}) if isinstance(entrega_json, dict) else {}
        item["cabecalho_partida"] = cab_partida
        item["cabecalho_entrega"] = cab_entrega
        item["status_label"] = "Em aberto" if item.get("viagem_aberta") else "Concluído"
        vehicle_ref = vehicles_lookup.get(item.get("veiculo_id"))
        item["veiculo"] = vehicle_ref

        if user.get("empresa") and (vehicle_ref or {}).get("empresa") != user["empresa"]:
            continue
        if user.get("area") and (vehicle_ref or {}).get("area") != user["area"]:
            continue

        filtered_data.append(item)

    return render_template("relatorios_list.html", relatorios=filtered_data)


@app.route("/admin/relatorios/<string:relatorio_id>")
@login_required("admin")
def relatorio_detalhe(relatorio_id: str):
    client = require_supabase()
    try:
        response = (
            client.table("relatorios")
            .select("id, relatorio_partida, relatorio_entrega, viagem_aberta, partida_at, entrega_at, created_at")
            .eq("id", relatorio_id)
            .limit(1)
            .execute()
        )
        record = response.data[0] if response.data else None
    except Exception:
        record = None

    if not record:
        flash("Relatório não encontrado.", "error")
        return redirect(url_for("historico_relatorios"))

    partida = record.get("relatorio_partida") or {}
    entrega = record.get("relatorio_entrega") or {}
    cab_partida = partida.get("cabecalho") or {}
    cab_entrega = entrega.get("cabecalho") or {}
    veiculo_id = partida.get("veiculo_id") if isinstance(partida, dict) else None
    veiculo = fetch_vehicle_details(client, veiculo_id)
    condutor_nome = (partida.get("condutor") or {}).get("nome") if isinstance(partida, dict) else None

    def align_by_label(part_list: list | None, ent_list: list | None, key: str) -> list:
        part_list = part_list or []
        ent_list = ent_list or []
        ent_map = {item.get(key): item for item in ent_list if isinstance(item, dict) and item.get(key)}
        seen = set()
        rows: list[dict] = []
        for item in part_list:
            if not isinstance(item, dict):
                continue
            label = item.get(key) or "-"
            rows.append({"label": label, "partida": item, "entrega": ent_map.get(item.get(key), {})})
            seen.add(item.get(key))
        for item in ent_list:
            if not isinstance(item, dict):
                continue
            label_key = item.get(key)
            if label_key not in seen:
                rows.append({"label": item.get(key) or "-", "partida": {}, "entrega": item})
        return rows

    componentes_alinhados = align_by_label(partida.get("componentes") if isinstance(partida, dict) else None, entrega.get("componentes") if isinstance(entrega, dict) else None, "nome")
    riscos_alinhados = align_by_label(partida.get("riscos") if isinstance(partida, dict) else None, entrega.get("riscos") if isinstance(entrega, dict) else None, "ponto")

    distancia_km = None
    try:
        km_inicial = int(cab_partida.get("km_inicial")) if cab_partida.get("km_inicial") is not None else None
        km_final = int(cab_entrega.get("km_final")) if cab_entrega.get("km_final") is not None else None
        if km_inicial is not None and km_final is not None:
            distancia_km = km_final - km_inicial
    except (TypeError, ValueError):
        distancia_km = None

    combustivel_saida = (partida.get("combustivel") or {}).get("saida") if isinstance(partida, dict) else None
    combustivel_chegada = (entrega.get("combustivel") or {}).get("chegada") if isinstance(entrega, dict) else None

    return render_template(
        "relatorio_detail.html",
        relatorio=record,
        veiculo=veiculo,
        partida=partida,
        entrega=entrega,
        cab_partida=cab_partida,
        cab_entrega=cab_entrega,
        condutor=condutor_nome,
        componentes_alinhados=componentes_alinhados,
        riscos_alinhados=riscos_alinhados,
        distancia_km=distancia_km,
        combustivel_saida=combustivel_saida,
        combustivel_chegada=combustivel_chegada,
    )


@app.route("/admin/avarias")
@login_required("admin")
def historico_avarias():
    client = require_supabase()
    try:
        data = (
            client.table("avaria")
            .select("id, created_at, veiculoID, userID, descricao, foto")
            .order("created_at", desc=True)
            .limit(200)
            .execute()
            .data
            or []
        )
    except Exception:
        # Fallback: some DB schemas use snake_case column names (veiculo_id, user_id).
        try:
            data = (
                client.table("avaria")
                .select("id, created_at, veiculo_id, user_id, descricao, foto")
                .order("created_at", desc=True)
                .limit(200)
                .execute()
                .data
                or []
            )
            data = _normalize_row_keys(data)
        except Exception:
            data = []
    # Resolve vehicle placa/model and user nome for display
    try:
        veiculo_ids = list({(item.get("veiculoID") or item.get("veiculo_id")) for item in data if (item.get("veiculoID") or item.get("veiculo_id"))})
        user_ids = list({(item.get("userID") or item.get("user_id")) for item in data if (item.get("userID") or item.get("user_id"))})
        veiculos_lookup: dict[str, dict] = {}
        usuarios_lookup: dict[str, dict] = {}
        if veiculo_ids:
            try:
                veiculos_resp = (
                    client.table("veiculo").select("id, placa, modelo").in_("id", veiculo_ids).execute().data or []
                )
                veiculos_lookup = {v["id"]: v for v in veiculos_resp}
            except Exception:
                veiculos_lookup = {}
        if user_ids:
            try:
                usuarios_resp = (
                    client.table("usuarios").select("id, nome").in_("id", user_ids).execute().data or []
                )
                usuarios_lookup = {u["id"]: u for u in usuarios_resp}
            except Exception:
                usuarios_lookup = {}

        for item in data:
            vid = item.get("veiculoID") or item.get("veiculo_id")
            uid = item.get("userID") or item.get("user_id")
            veiculo_ref = veiculos_lookup.get(vid)
            usuario_ref = usuarios_lookup.get(uid)
            # Prefer showing 'modelo · placa' when available, fallback to id
            if veiculo_ref:
                modelo = (veiculo_ref.get("modelo") or "").strip()
                placa = (veiculo_ref.get("placa") or "").strip()
                item["veiculoID"] = f"{modelo} · {placa}" if modelo or placa else vid
            else:
                item["veiculoID"] = vid
            item["userID"] = (usuario_ref or {}).get("nome") or uid
    except Exception:
        # If lookups fail, leave IDs as-is
        pass

    return render_template("avarias_list.html", avarias=data)


@app.route("/admin/usuarios")
@login_required("admin")
def lista_usuarios():
    client = require_supabase()
    user = session.get("user") or {}
    query = client.table("usuarios").select("id, nome, email, empresa, area, autorizado, created_at")

    if user.get("empresa"):
        query = query.eq("empresa", user["empresa"])
    if user.get("area"):
        query = query.eq("area", user["area"])

    data = (
        query
        .order("created_at", desc=True)
        .limit(200)
        .execute()
        .data
        or []
    )
    return render_template("usuarios_list.html", usuarios=data)


@app.route("/admin/usuarios/<string:user_id>/status", methods=["POST"])
@login_required("admin")
def atualizar_status_usuario(user_id: str):
    client = require_supabase()
    try:
        payload = request.get_json()
        autorizado = payload.get("autorizado", False)
        client.table("usuarios").update({"autorizado": autorizado}).eq("id", user_id).execute()
        return {"success": True}, 200
    except Exception as exc:  # pragma: no cover
        return {"error": str(exc)}, 400


@app.route("/admin/usuarios/<string:user_id>/edit", methods=["POST"])
@login_required("admin")
def editar_usuario(user_id: str):
    client = require_supabase()
    try:
        payload = request.get_json()
        nome = payload.get("nome", "").strip()
        empresa = payload.get("empresa", "").strip()
        area = payload.get("area", "").strip()
        
        if not nome:
            return {"error": "Nome é obrigatório"}, 400
        
        client.table("usuarios").update({
            "nome": nome,
            "empresa": empresa,
            "area": area
        }).eq("id", user_id).execute()
        
        return {"success": True}, 200
    except Exception as exc:  # pragma: no cover
        return {"error": str(exc)}, 400


@app.route("/admin/usuarios/<string:user_id>", methods=["DELETE"])
@login_required("admin")
def deletar_usuario(user_id: str):
    client = require_supabase()
    try:
        # Deleta o usuário da tabela usuarios
        client.table("usuarios").delete().eq("id", user_id).execute()
        
        # Deleta a conta do usuário do Supabase Auth (opcional, pode causar erro se não existir)
        if supabase_service:
            try:
                supabase_service.auth.admin.delete_user(user_id)
            except Exception:
                pass  # Se falhar, continua de qualquer forma
        
        return {"success": True}, 200
    except Exception as exc:  # pragma: no cover
        return {"error": str(exc)}, 400


@app.route("/admin/veiculos", methods=["GET", "POST"])
@login_required("admin")
def gerenciar_veiculos():
    client = require_supabase()
    if request.method == "POST":
        placa = request.form.get("placa", "").upper()
        modelo = request.form.get("modelo")
        marca = request.form.get("marca")
        tipo = request.form.get("tipo")
        combustivel = request.form.get("combustivel")
        foto = request.files.get("foto_veiculo")
        
        # Validar todos os campos obrigatórios
        if not placa or not modelo or not tipo or not combustivel:
            flash("Informe placa, modelo, tipo e combustível.", "error")
            return redirect(url_for("gerenciar_veiculos"))
        
        # Validar se a foto foi enviada
        if not foto or not foto.filename:
            flash("Foto é obrigatória para cadastrar um veículo.", "error")
            return redirect(url_for("gerenciar_veiculos"))
        
        # Obter empresa e area do usuário logado
        user = session.get("user") or {}
        empresa = user.get("empresa")
        area = user.get("area")
        
        inserted = (
            client.table("veiculo")
            .insert({
                "placa": placa,
                "modelo": modelo,
                "marca": marca,
                "tipo": tipo,
                "combustivel": combustivel,
                "empresa": empresa,
                "area": area
            })
            .execute()
            .data
        )
        veiculo_id = inserted[0]["id"] if inserted else None
        if veiculo_id and foto and foto.filename:
            upload_image("veiculos", foto, f"{veiculo_id}")
        flash("Veículo cadastrado!", "success")
        return redirect(url_for("gerenciar_veiculos"))

    # Filtrar veículos por empresa e area do usuário
    user = session.get("user") or {}
    query = client.table("veiculo").select("id, placa, modelo, marca, tipo, combustivel, empresa, area, created_at")
    
    if user.get("empresa"):
        query = query.eq("empresa", user["empresa"])
    if user.get("area"):
        query = query.eq("area", user["area"])
    
    veiculos = (
        query
        .order("created_at", desc=True)
        .execute()
        .data
        or []
    )

    # KM rodado por veículo a partir dos relatórios (km_final - km_inicial)
    km_por_veiculo: dict[str, int] = {}
    try:
        relatorios = (
            client.table("relatorios")
            .select("relatorio_partida, relatorio_entrega")
            .limit(1000)
            .execute()
            .data
            or []
        )
        for rel in relatorios:
            partida = rel.get("relatorio_partida") or {}
            entrega = rel.get("relatorio_entrega") or {}
            if not isinstance(partida, dict):
                continue
            veiculo_rel = partida.get("veiculo_id") or partida.get("veiculoID")
            if not veiculo_rel:
                continue
            cab_p = partida.get("cabecalho") or {}
            cab_e = entrega.get("cabecalho") or {}
            try:
                km_i = int(cab_p.get("km_inicial")) if cab_p.get("km_inicial") is not None else None
                km_f = int(cab_e.get("km_final")) if cab_e.get("km_final") is not None else None
                if km_i is None or km_f is None:
                    continue
                km_por_veiculo[veiculo_rel] = km_por_veiculo.get(veiculo_rel, 0) + (km_f - km_i)
            except (TypeError, ValueError):
                continue
    except Exception:
        # Se falhar, seguimos sem o agregado de km
        pass

    tipo_lookup = {item["id"]: item["label"] for item in VEICULO_TIPOS}
    combustivel_lookup = {item["id"]: item["label"] for item in VEICULO_COMBUSTIVEIS}
    brand_lookup = {brand["label"].lower(): brand for brand in VEICULO_MARCAS}
    model_lookup = {}
    for brand in VEICULO_MARCAS:
        for model in brand["models"]:
            model_lookup[model["label"].lower()] = {"model": model, "brand": brand}

    for item in veiculos:
        item["foto_url"] = fetch_vehicle_photo(item["id"])
        item["tipo_label"] = tipo_lookup.get(item.get("tipo"), item.get("tipo") or "-")
        item["combustivel_label"] = combustivel_lookup.get(item.get("combustivel"), item.get("combustivel") or "-")
        item["km_rodado"] = km_por_veiculo.get(item["id"], 0)
        marca_label = (item.get("marca") or "").strip()
        modelo_label = (item.get("modelo") or "").strip()

        brand_match = brand_lookup.get(marca_label.lower()) if marca_label else None
        model_match = model_lookup.get(modelo_label.lower()) if modelo_label else None

        item["marca_id"] = brand_match["id"] if brand_match else (model_match["brand"]["id"] if model_match else "")
        item["modelo_id"] = model_match["model"]["id"] if model_match else ""

        if model_match and not item.get("tipo"):
            item["tipo"] = model_match["model"]["tipo_id"]
            item["tipo_label"] = tipo_lookup.get(item["tipo"], item["tipo"])

    # Ordenar por km rodado (desc)
    veiculos.sort(key=lambda v: v.get("km_rodado") or 0, reverse=True)

    return render_template(
        "veiculos.html",
        veiculos=veiculos,
        marcas=VEICULO_MARCAS,
        tipos=VEICULO_TIPOS,
        combustiveis=VEICULO_COMBUSTIVEIS,
    )


@app.route("/admin/veiculos/<string:veiculo_id>", methods=["POST"])
@login_required("admin")
def atualizar_veiculo(veiculo_id: str):
    client = require_supabase()
    payload = {
        "placa": request.form.get("placa", "").upper(),
        "modelo": request.form.get("modelo"),
        "marca": request.form.get("marca"),
        "tipo": request.form.get("tipo"),
        "combustivel": request.form.get("combustivel"),
    }
    client.table("veiculo").update(payload).eq("id", veiculo_id).execute()
    foto = request.files.get("foto_veiculo")
    if foto and foto.filename:
        upload_image("veiculos", foto, f"{veiculo_id}")
    flash("Veículo atualizado.", "success")
    return redirect(url_for("gerenciar_veiculos"))


@app.route("/admin/veiculos/<string:veiculo_id>/edit", methods=["POST"])
@login_required("admin")
def editar_veiculo_ajax(veiculo_id: str):
    client = require_supabase()
    try:
        payload = request.get_json(silent=True) or {}
        placa = (payload.get("placa") or "").strip().upper()
        modelo = (payload.get("modelo") or "").strip()
        marca = (payload.get("marca") or "").strip()
        tipo = (payload.get("tipo") or "").strip()
        combustivel = (payload.get("combustivel") or "").strip()

        if not placa or not modelo:
            return {"error": "Placa e modelo são obrigatórios."}, 400

        empresa = payload.get("empresa", "").strip()
        area = payload.get("area", "").strip()
        
        update_payload = {
            "placa": placa,
            "modelo": modelo,
            "marca": marca,
            "tipo": tipo,
            "combustivel": combustivel,
            "empresa": empresa or None,
            "area": area or None,
        }

        client.table("veiculo").update(update_payload).eq("id", veiculo_id).execute()
        return {"success": True}, 200
    except Exception as exc:  # pragma: no cover
        return {"error": str(exc)}, 400


@app.route("/admin/veiculos/<string:veiculo_id>/delete", methods=["DELETE"])
@login_required("admin")
def deletar_veiculo_ajax(veiculo_id: str):
    client = require_supabase()
    try:
        client.table("veiculo").delete().eq("id", veiculo_id).execute()
        delete_vehicle_photos(veiculo_id)
        return {"success": True}, 200
    except Exception as exc:  # pragma: no cover
        return {"error": str(exc)}, 400


def fetch_vehicle_photo(veiculo_id: str) -> str | None:
    storage = require_supabase().storage.from_("veiculos")
    try:
        files = storage.list(veiculo_id)
    except Exception:
        return None
    if not files:
        return None
    first = files[0]
    path = f"{veiculo_id}/{first['name']}"
    return storage.get_public_url(path)


def _normalize_row_keys(rows: list[dict]) -> list[dict]:
    """Normalize returned row keys: convert snake_case to camelCase keys expected by the code.

    This helps when the database schema uses snake_case (veiculo_id, user_id)
    but the application expects camelCase (veiculoID, userID).
    """
    if not rows:
        return rows
    for row in rows:
        if isinstance(row, dict):
            if row.get('veiculo_id') is not None and row.get('veiculoID') is None:
                row['veiculoID'] = row.get('veiculo_id')
            if row.get('user_id') is not None and row.get('userID') is None:
                row['userID'] = row.get('user_id')
    return rows


def delete_vehicle_photos(veiculo_id: str) -> None:
    storage = require_supabase().storage.from_("veiculos")
    try:
        files = storage.list(veiculo_id)
    except Exception:
        return
    if not files:
        return
    paths = [f"{veiculo_id}/{entry['name']}" for entry in files]
    try:
        storage.remove(paths)
    except Exception:
        pass


@app.route("/avarias/novo", methods=["GET", "POST"])
@login_required()
def registrar_avaria():
    client = require_supabase()
    user = session.get("user")
    
    # Filtrar veículos por empresa e area do usuário
    query = client.table("veiculo").select("id, placa, modelo")
    
    if user.get("empresa"):
        query = query.eq("empresa", user["empresa"])
    if user.get("area"):
        query = query.eq("area", user["area"])
    
    veiculos = (
        query
        .order("modelo")
        .execute()
        .data
        or []
    )
    if request.method == "POST":
        veiculo_id = request.form.get("veiculo_id")
        data_hora_avaria = request.form.get("data_hora_avaria")
        
        if not veiculo_id:
            flash("Selecione um veículo.", "error")
            return redirect(url_for("registrar_avaria"))
        
        if not data_hora_avaria:
            flash("Informe a data e horário da constatação.", "error")
            return redirect(url_for("registrar_avaria"))
        
        descricao_list = request.form.getlist("avaria_descricao[]")
        local_list = request.form.getlist("avaria_local[]")
        fotos = request.files.getlist("avaria_foto[]")
        
        avarias_registradas = 0
        for idx, descricao in enumerate(descricao_list):
            descricao = descricao.strip()
            foto = fotos[idx] if idx < len(fotos) else None
            local = local_list[idx] if idx < len(local_list) else None
            
            if not descricao and (not foto or not foto.filename):
                continue
                
            foto_url = None
            if foto and foto.filename:
                foto_url = upload_image(
                    bucket="avarias",
                    file_storage=foto,
                    prefix=f"{veiculo_id}/{uuid.uuid4()}",
                )
            
            client.table("avaria").insert(
                {
                    "veiculoID": veiculo_id,
                    "userID": session["user"]["id"],
                    "descricao": descricao or local,
                    "foto": foto_url,
                }
            ).execute()
            avarias_registradas += 1
        
        if avarias_registradas > 0:
            flash(f"{avarias_registradas} avaria(s) registrada(s) com sucesso!", "success")
        else:
            flash("Preencha pelo menos uma avaria com descrição e foto.", "error")
            return redirect(url_for("registrar_avaria"))
        
        return redirect(url_for("dashboard"))
    
    return render_template("avarias_form.html", veiculos=veiculos)


@app.route("/abastecimentos/novo", methods=["GET", "POST"])
@login_required()
def registrar_abastecimento():
    client = require_supabase()
    user = session.get("user")
    
    # Filtrar veículos por empresa e area do usuário
    query = client.table("veiculo").select("id, placa, modelo")
    
    if user.get("empresa"):
        query = query.eq("empresa", user["empresa"])
    if user.get("area"):
        query = query.eq("area", user["area"])
    
    veiculos = (
        query
        .order("modelo")
        .execute()
        .data
        or []
    )
    if request.method == "POST":
        veiculo_id = request.form.get("veiculo_id")
        data_abastecimento = request.form.get("data") or datetime.utcnow().isoformat()
        km = request.form.get("km")
        valor = request.form.get("valor")
        litros = request.form.get("litros")
        nota_texto = request.form.get("nota_texto")
        abastecimento_id = str(uuid.uuid4())
        foto_km = request.files.get("foto_km")
        foto_nota = request.files.get("foto_nota")
        foto_km_url = upload_image("abastecimentos", foto_km, f"{abastecimento_id}/km") if foto_km else None
        foto_nota_url = upload_image("abastecimentos", foto_nota, f"{abastecimento_id}/nota") if foto_nota else None
        nota_payload = {
            "texto": nota_texto,
            "foto_nota_url": foto_nota_url,
            "foto_km_url": foto_km_url,
        }
        client.table("abastecimentos").insert(
            {
                "id": abastecimento_id,
                "veiculoID": veiculo_id,
                "userID": session["user"]["id"],
                "data": data_abastecimento,
                "km": int(km) if km else None,
                "valor": float(valor) if valor else None,
                "litros": float(litros) if litros else None,
                "nota": json.dumps(nota_payload),
            }
        ).execute()
        flash("Abastecimento registrado!", "success")
        # Redireciona para o dashboard adequado conforme o perfil
        return redirect(url_for("dashboard"))

    return render_template("abastecimentos_form.html", veiculos=veiculos)


@app.route("/abastecimentos/historico")
@login_required()
def historico_abastecimentos():
    client = require_supabase()
    try:
        data = (
            client.table("abastecimentos")
            .select("id, created_at, data, veiculoID, km, valor, litros, nota, userID")
            .order("data", desc=True)
            .limit(200)
            .execute()
            .data
            or []
        )
    except Exception:
        try:
            data = (
                client.table("abastecimentos")
                .select("id, created_at, data, veiculo_id, km, valor, litros, nota, user_id")
                .order("data", desc=True)
                .limit(200)
                .execute()
                .data
                or []
            )
            data = _normalize_row_keys(data)
        except Exception:
            data = []
    veiculos_lookup = {}
    usuarios_lookup = {}
    try:
        veiculos_data = (
            client.table("veiculo")
            .select("id, placa")
            .execute()
            .data
            or []
        )
        veiculos_lookup = {item["id"]: item for item in veiculos_data}
        usuarios_data = (
            client.table("usuarios")
            .select("id, nome")
            .execute()
            .data
            or []
        )
        usuarios_lookup = {item["id"]: item for item in usuarios_data}
    except Exception:
        pass

    for item in data:
        try:
            nota_json = json.loads(item.get("nota") or "{}")
        except json.JSONDecodeError:
            nota_json = {"texto": item.get("nota")}
        item["nota_json"] = nota_json
        veiculo_ref = veiculos_lookup.get(item.get("veiculoID"))
        item["veiculo_placa"] = (veiculo_ref or {}).get("placa")
        usuario_ref = usuarios_lookup.get(item.get("userID"))
        item["usuario_nome"] = (usuario_ref or {}).get("nome")
        data_raw = item.get("data")
        data_formatada = None
        if data_raw:
            iso_value = data_raw.rstrip("Z")
            try:
                parsed = datetime.fromisoformat(iso_value)
                data_formatada = parsed.strftime("%d/%m/%Y - %H:%M")
            except ValueError:
                data_formatada = None
        item["data_formatada"] = data_formatada or data_raw or "-"
    return render_template("abastecimentos_history.html", abastecimentos=data)


@app.errorhandler(404)
def not_found(_):
    return render_template("404.html"), 404


@app.errorhandler(500)
def server_error(error):
    return render_template("500.html", error=error), 500


if __name__ == "__main__":
    debug_mode = os.getenv("FLASK_DEBUG", "0") == "1"
    print("=" * 60)
    print("TRIVIA KM - TRIVIA TRENS")
    print("=" * 60)
    print("\n[OK] Servidor iniciado")
    print(f"[OK] Porta: {int(os.getenv('PORT', '5000'))}")
    print(f"[OK] Debug: {debug_mode}")
    print(f"\n[INFO] Acesse: http://localhost:{int(os.getenv('PORT', '5000'))}")
    print("=" * 60)
    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", "5000")),
        debug=debug_mode,
        use_reloader=debug_mode,
    )
