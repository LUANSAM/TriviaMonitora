import json
import math
import os
import secrets
import uuid
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from datetime import datetime, timezone, timedelta
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
    jsonify,
)
from supabase import create_client, Client
from werkzeug.utils import secure_filename
import certifi
import re
from urllib.parse import quote_plus

DOTENV_PATH = os.path.join(os.path.dirname(__file__), ".env")
# Garante que o .env local sobrescreva variaveis ja definidas no ambiente.
load_dotenv(dotenv_path=DOTENV_PATH, override=True)

try:
    CERT_PATH = certifi.where()
    os.environ["SSL_CERT_FILE"] = CERT_PATH
    os.environ["REQUESTS_CA_BUNDLE"] = CERT_PATH
except Exception:
    pass

SUPABASE_URL = os.getenv("SUPABASE_URL","https://roawjxyftfntldpdqlee.supabase.co")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY","eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJvYXdqeHlmdGZudGxkcGRxbGVlIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjAzOTI5OTcsImV4cCI6MjA3NTk2ODk5N30.vPNSc4n4wG9V-nxqtPEMiwI88K0ExdQillcCTnv2WyI")
SUPABASE_SERVICE_ROLE = os.getenv("SUPABASE_SERVICE_ROLE","eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJvYXdqeHlmdGZudGxkcGRxbGVlIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2MDM5Mjk5NywiZXhwIjoyMDc1OTY4OTk3fQ.16UYRCE-m9B2L-5VOxsOoWzpcnFGolm-3jph2k966NM")
SUPABASE_FORCE_MOCK = os.getenv("SUPABASE_FORCE_MOCK", "0") == "1"

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", secrets.token_hex(32))
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024  # 25MB uploads
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = False  # Para dev local (http)
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=7)

# Atualize estas listas para controlar as opções dos dropdowns da tela de cadastro.
REGISTER_COMPANIES = [
    {"id": "trivia_trens", "label": "Trivia Trens"},
    {"id": "tic_trens", "label": "Tic Trens"},
    {"id": "metro_bh", "label": "Metrô BH"},
]

REGISTER_AREAS = [
    {"id": "restabelecimento", "label": "Restabelecimento"},
    {"id": "energia", "label": "Energia"},
    {"id": "telecom_sinalizacao", "label": "Telecom/Sinalização"},
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

# Comentado: service role lazy loading também
# if SUPABASE_URL and SUPABASE_SERVICE_ROLE:
#     try:
#         supabase_service = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE)
#     except Exception:
#         supabase_service = None


LOCOMOTIVA_COMBUSTIVEIS = [
    {"id": "diesel_s10", "label": "Diesel S10"},
    {"id": "diesel_s500", "label": "Diesel S500"},
]

LOCOMOTIVA_COMBUSTIVEL_LABELS = {item["label"] for item in LOCOMOTIVA_COMBUSTIVEIS}

# Atualize esta lista para controlar as opções do dropdown de base no cadastro/edição de locomotivas.
LOCOMOTIVA_BASES = [
    {"id": "patio_calmon", "label": "Calmon Viana"},
    {"id": "patio_lapa", "label": "Lapa"},
    {"id": "patio_isp", "label": "Eng. São Paulo"},
]

LOCOMOTIVA_BASE_LABELS = {item["label"] for item in LOCOMOTIVA_BASES}


LEVEL_STATUS_COLORS = {
    "safe": "#1ec592",
    "moderate": "#f6c343",
    "alert": "#f36405",
    "critical": "#ff0000",
    "unknown": "#95a1b3",
}

# Horário oficial de Brasília (UTC-3)
BRT_TZ = timezone(timedelta(hours=-3))


def build_user_profile_payload(
    user_id: str,
    nome: str,
    email: str,
    empresa: str,
    area: str,
) -> dict:
    """Montar os campos exigidos pela tabela usuarios após o cadastro."""
    timestamp_now = datetime.now(timezone.utc).isoformat()
    return {
        "id": user_id,
        "nome": nome,
        "email": email,
        "empresa": empresa or None,
        "area": area or None,
        "autorizado": True,
        "role": "Usuário",
        "ultimoAcesso": timestamp_now,
    }


def _safe_float(value) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize_level_percentage(value) -> float | None:
    raw = _safe_float(value)
    if raw is None:
        return None
    if 0 <= raw <= 1:
        raw *= 100
    return max(min(raw, 100.0), 0.0)


def _classify_level_status(percent: float | None) -> str:
    if percent is None:
        return "unknown"
    if percent >= 70:
        return "safe"
    if percent >= 40:
        return "moderate"
    if percent >= 20:
        return "alert"
    return "critical"


def _parse_datetime(value):
    if not value:
        return None
    if isinstance(value, datetime):
        dt_value = value
    else:
        text = value
        if isinstance(text, str) and text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            dt_value = datetime.fromisoformat(text)
        except Exception:
            return None
    if dt_value.tzinfo is None:
        # Assume registros sem timezone já estão em horário de Brasília
        dt_value = dt_value.replace(tzinfo=BRT_TZ)
    return dt_value


def _format_datetime_display(dt_value):
    if not dt_value:
        return None
    return dt_value.astimezone(BRT_TZ).strftime("%d/%m/%Y - %H:%M")


def _should_display_level(raw) -> bool:
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, str):
        return raw.strip().lower() in {"true", "1", "t", "y", "yes"}
    if isinstance(raw, (int, float)):
        return raw == 1 or raw is True
    return False


def _coerce_mapping(value) -> dict:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            return {}
    return {}


def fetch_generator_levels() -> list[dict]:
    print("[DEBUG] Iniciando carga de níveis de combustível", flush=True)
    
    # Usar dados mockados se a flag estiver ativada ou se as credenciais do Supabase
    # não estiverem presentes nas variáveis de ambiente (útil para deploys em cloud).
    if SUPABASE_FORCE_MOCK or not (SUPABASE_URL and SUPABASE_ANON_KEY):
        print("[INFO] SUPABASE_FORCE_MOCK=1 ou credenciais Supabase faltando, usando dados mockados", flush=True)
        return _get_mock_fuel_data()
    
    try:
        print("[DEBUG] Tentando obter cliente Supabase...", flush=True)
        client = require_supabase()
        print("[DEBUG] Supabase client obtido com sucesso", flush=True)
    except RuntimeError as exc:
        print(f"[WARN] Supabase indisponível, usando dados mockados: {exc}", flush=True)
        # Fallback: retornar dados mockados quando Supabase não estiver disponível
        return _get_mock_fuel_data()

    def _load_levels() -> list[dict]:
        print("[DEBUG] Consultando tabela equipamentos...", flush=True)
        response = (
            client.table("equipamentos")
            .select("id, nome, tipo, exibeNivel, nivelAtual, ultimaAtualizacao, dados, estacao, local")
            .eq("tipo", "Gerador")
            .eq("exibeNivel", True)
            .order("nome", desc=False)
            .execute()
        )
        rows = response.data or []
        print(f"[DEBUG] Query retornou {len(rows)} equipamentos", flush=True)
        return rows

    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_load_levels)
            rows = future.result(timeout=6)
    except FuturesTimeout:
        print("[WARN] Query de níveis excedeu 6s, usando dados mockados", flush=True)
        return _get_mock_fuel_data()
    except Exception as exc:
        print(f"[WARN] Erro ao consultar níveis de combustível, usando dados mockados: {exc}", flush=True)
        return _get_mock_fuel_data()

    levels: list[dict] = []
    now_utc = datetime.now(timezone.utc)
    now_brt = now_utc.astimezone(BRT_TZ)
    now_brt_display = now_brt.strftime("%d/%m/%Y - %H:%M")
    for row in rows:
        if not _should_display_level(row.get("exibeNivel")):
            continue

        print(f"[DEBUG] Processando equipamento {row.get('id')} - exibeNivel ok", flush=True)

        data = _coerce_mapping(row.get("dados"))
        estacao_meta = _coerce_mapping(row.get("estacao"))

        level_raw = _safe_float(row.get("nivelAtual"))
        level_percent = _normalize_level_percentage(level_raw)
        level_status = _classify_level_status(level_percent)
        level_ratio = (level_percent / 100.0) if level_percent is not None else None

        autonomia_base = _safe_float(data.get("autonomia"))
        autonomia_total = None
        if autonomia_base is not None and level_ratio is not None:
            autonomia_total = round(level_ratio * autonomia_base, 1)

        # Calculate fuel capacity in liters
        tanque_capacidade = _safe_float(data.get("tanque"))
        litros_disponiveis = None
        volume_atual = None
        volume_para_completar = None
        if tanque_capacidade is not None and level_ratio is not None:
            volume_atual = round(level_ratio * tanque_capacidade, 1)
            volume_para_completar = max(0.0, round(tanque_capacidade - (level_ratio * tanque_capacidade), 1))
            litros_disponiveis = tanque_capacidade - math.ceil(level_ratio * tanque_capacidade)

        ultima_dt = _parse_datetime(row.get("ultimaAtualizacao"))
        is_online = False
        status_label = "offline"
        ultima_diff_minutes = None
        ultima_diff_display = None
        if ultima_dt:
            delta = now_utc - ultima_dt
            if delta <= timedelta(minutes=2):
                is_online = True
                status_label = "online"
            ultima_diff_minutes = round(delta.total_seconds() / 60.0, 1)
            ultima_diff_display = f"{ultima_diff_minutes:.1f} min"
        location_value = estacao_meta.get("estacao")
        if not location_value and isinstance(row.get("estacao"), str):
            location_value = row.get("estacao")
        is_critical_focus = level_percent is not None and level_percent < 25

        # Prepare address / maps URL using address fields inside `local` (if present)
        local_data = _coerce_mapping(row.get("local"))
        endereco_parts = []
        try:
            # `local_data` is the parsed JSONB from `local` column
            for k in ("rua", "numero", "bairro", "cidade", "cep"):
                v = local_data.get(k) if isinstance(local_data, dict) else None
                if v:
                    endereco_parts.append(str(v).strip())
        except Exception as e:
            print(f"[WARN] Erro ao processar endereço para {row.get('id')}: {e}", flush=True)
            endereco_parts = []

        endereco_text = ", ".join(endereco_parts).strip() if endereco_parts else None
        maps_url = None
        if endereco_text:
            maps_url = f"https://www.google.com/maps/search/?api=1&query={quote_plus(endereco_text)}"

        levels.append(
            {
                "id": row.get("id"),
                "nome": row.get("nome") or "Gerador",
                "nivel_percent": level_percent,
                "nivel_display": f"{level_percent:.0f}%" if level_percent is not None else "—",
                "nivel_status": level_status,
                "level_color": (
                    LEVEL_STATUS_COLORS["critical"]
                    if (level_percent is not None and level_percent < 25)
                    else LEVEL_STATUS_COLORS.get(level_status, LEVEL_STATUS_COLORS["unknown"])
                ),
                "is_critical_focus": is_critical_focus,
                "autonomia_value": autonomia_total,
                "autonomia_display": f"{autonomia_total:.1f} h" if autonomia_total is not None else None,
                "volume_tanque": tanque_capacidade,
                "volume_atual": volume_atual,
                "volume_para_completar": volume_para_completar,
                "litros_disponiveis": litros_disponiveis,
                "local": location_value or "Local não informado",
                "dados": data,
                "maps_url": maps_url,
                "ultima_atualizacao_dt": ultima_dt,
                # Normalize display string and remove any trailing 'UTC' label
                "ultima_atualizacao_display": (lambda v: (v.replace(" UTC", "").replace("UTC", "").strip()) if v else None)(_format_datetime_display(ultima_dt) or row.get("ultimaAtualizacao")),
                "ultima_atualizacao_iso": ultima_dt.isoformat() if ultima_dt else row.get("ultimaAtualizacao"),
                "status_online": is_online,
                "status_label": status_label,
                "ultima_diff_minutes": ultima_diff_minutes,
                "ultima_diff_display": ultima_diff_display,
                "brasilia_now_display": now_brt_display,
            }
        )

    print(f"[DEBUG] Total de {len(levels)} geradores processados para exibição", flush=True)
    return levels


def _get_mock_fuel_data() -> list[dict]:
    """Retorna dados mockados para teste quando Supabase não está disponível."""
    now_brt = datetime.now(timezone.utc).astimezone(BRT_TZ)
    now_brt_display = now_brt.strftime("%d/%m/%Y - %H:%M")

    def mock_entry(**kwargs):
        base = {
            "status_online": False,
            "status_label": "offline",
            "ultima_diff_minutes": None,
            "ultima_diff_display": "—",
            "brasilia_now_display": now_brt_display,
            "ultima_atualizacao_dt": None,
        }
        base.update(kwargs)
        return base

    items = [
        mock_entry(
            id=1,
            nome="Gerador Principal - Sede (MOCK)",
            nivel_percent=85.5,
            nivel_display="86%",
            nivel_status="safe",
            level_color=LEVEL_STATUS_COLORS["safe"],
            is_critical_focus=False,
            autonomia_value=34.2,
            autonomia_display="34.2 h",
            volume_tanque="500L",
            litros_disponiveis=428,
            local="Estação Central - Sala Técnica",
            ultima_atualizacao_display="15/02/2026 19:50",
            ultima_atualizacao_iso="2026-02-15T19:50:00",
        ),
        mock_entry(
            id=2,
            nome="Gerador Backup - Norte (MOCK)",
            nivel_percent=45.2,
            nivel_display="45%",
            nivel_status="moderate",
            level_color=LEVEL_STATUS_COLORS["moderate"],
            is_critical_focus=False,
            autonomia_value=18.1,
            autonomia_display="18.1 h",
            volume_tanque="300L",
            litros_disponiveis=136,
            local="Terminal Norte",
            ultima_atualizacao_display="15/02/2026 19:45",
            ultima_atualizacao_iso="2026-02-15T19:45:00",
        ),
        mock_entry(
            id=3,
            nome="Gerador Emergência - Sul (MOCK)",
            nivel_percent=22.8,
            nivel_display="23%",
            nivel_status="alert",
            level_color=LEVEL_STATUS_COLORS["alert"],
            is_critical_focus=True,
            autonomia_value=9.1,
            autonomia_display="9.1 h",
            volume_tanque="400L",
            litros_disponiveis=92,
            local="Terminal Sul - Subsolo",
            ultima_atualizacao_display="15/02/2026 19:40",
            ultima_atualizacao_iso="2026-02-15T19:40:00",
        ),
        mock_entry(
            id=4,
            nome="Gerador Crítico - Leste (MOCK)",
            nivel_percent=8.5,
            nivel_display="9%",
            nivel_status="critical",
            level_color=LEVEL_STATUS_COLORS["critical"],
            is_critical_focus=True,
            autonomia_value=3.4,
            autonomia_display="3.4 h",
            volume_tanque="250L",
            litros_disponiveis=22,
            local="Estação Leste",
            ultima_atualizacao_display="15/02/2026 19:35",
            ultima_atualizacao_iso="2026-02-15T19:35:00",
        ),
    ]

    for item in items:
        capacidade = _safe_float(item.get("volume_tanque"))
        nivel_percent = _safe_float(item.get("nivel_percent"))
        nivel_ratio = (nivel_percent / 100.0) if nivel_percent is not None else None
        volume_atual = None
        volume_para_completar = None
        if capacidade is not None and nivel_ratio is not None:
            volume_atual = round(nivel_ratio * capacidade, 1)
            volume_para_completar = max(0.0, round(capacidade - (nivel_ratio * capacidade), 1))
            if item.get("litros_disponiveis") is None:
                item["litros_disponiveis"] = math.ceil(volume_para_completar)
        item["volume_tanque"] = capacidade
        item["volume_atual"] = volume_atual
        item["volume_para_completar"] = volume_para_completar

    return items


def fetch_operacao_elevadores() -> list[dict]:
    client = get_supabase_service() or require_supabase()
    now_utc = datetime.now(timezone.utc)

    try:
        response = (
            client.table("equipamentos")
            .select("id, nome, tipo, local, estacao, ultimaAtualizacao, estado")
            .eq("tipo", "Elevador")
            .order("nome", desc=False)
            .execute()
        )
        rows = response.data or []
    except Exception as exc:
        print(f"[WARN] Erro ao consultar elevadores para operação: {exc}", flush=True)
        return []

    equipamentos: list[dict] = []
    for row in rows:
        ultima_dt = _parse_datetime(row.get("ultimaAtualizacao"))
        is_online = False
        ultima_diff_minutes = None
        if ultima_dt:
            delta = now_utc - ultima_dt
            is_online = delta <= timedelta(minutes=2)
            ultima_diff_minutes = round(delta.total_seconds() / 60.0, 1)

        local_data = _coerce_mapping(row.get("local"))
        estacao_data = _coerce_mapping(row.get("estacao"))
        local_display = None
        if isinstance(estacao_data, dict):
            local_display = estacao_data.get("estacao")
        if isinstance(local_data, dict):
            local_display = local_display or (
                local_data.get("estacao")
                or local_data.get("nome")
                or local_data.get("codigo")
            )
        if not local_display and isinstance(row.get("local"), str):
            local_display = row.get("local")
        if not local_display and isinstance(row.get("estacao"), str):
            local_display = row.get("estacao")
        local_display = str(local_display).strip() if local_display else ""

        endereco_parts = []
        if isinstance(local_data, dict):
            for key in ("rua", "numero", "bairro", "cidade", "cep"):
                value = local_data.get(key)
                if value:
                    endereco_parts.append(str(value).strip())
        endereco_text = ", ".join(endereco_parts).strip() if endereco_parts else local_display
        maps_url = (
            f"https://www.google.com/maps/search/?api=1&query={quote_plus(endereco_text)}"
            if endereco_text
            else None
        )

        estado_raw = row.get("estado")
        if isinstance(estado_raw, bool):
            estado_ativo = estado_raw
        elif isinstance(estado_raw, str):
            estado_ativo = estado_raw.strip().lower() in {"true", "1", "t", "yes", "y"}
        elif isinstance(estado_raw, (int, float)):
            estado_ativo = int(estado_raw) == 1
        else:
            estado_ativo = False

        equipamentos.append(
            {
                "id": row.get("id"),
                "nome": row.get("nome") or "Elevador",
                "local": local_display,
                "maps_url": maps_url,
                "status_online": is_online,
                "status_label": "online" if is_online else "offline",
                "ultima_diff_minutes": ultima_diff_minutes,
                "ultima_atualizacao_display": _format_datetime_display(ultima_dt) or row.get("ultimaAtualizacao"),
                "estado_ativo": estado_ativo,
                "estado_label": "ATIVADO" if estado_ativo else "DESATIVADO",
            }
        )

    return equipamentos


def _is_superadm_session() -> bool:
    session_user = session.get("user") or {}
    return (session_user.get("role") or "").strip().lower() == "superadm"


def fetch_locomotivas_admin(
    search_term: str | None = None,
    sort_by: str = "modelo",
    sort_dir: str = "asc",
    page: int = 1,
    per_page: int = 10,
) -> dict:
    client = get_supabase_service() or require_supabase()
    try:
        response = (
            client.table("locomotivas")
            .select("id, tag, modelo, base, combustivel, volume_tanque, nivel_atual")
            .order("tag", desc=False)
            .limit(500)
            .execute()
        )
        rows = response.data or []
    except Exception as exc:
        print(f"[WARN] Erro ao consultar locomotivas: {exc}", flush=True)
        return {"items": [], "total": 0, "total_pages": 1, "page": 1}

    query = (search_term or "").strip().lower()
    locomotivas: list[dict] = []
    for row in rows:
        tag_value = str(row.get("tag") or "").strip()
        modelo_value = str(row.get("modelo") or "").strip()
        base_value = str(row.get("base") or "").strip()
        combustivel_value = str(row.get("combustivel") or "").strip()
        tanque_value = _safe_float(row.get("volume_tanque"))
        nivel_value = _normalize_level_percentage(_safe_float(row.get("nivel_atual")))

        if query:
            haystack = f"{tag_value} {modelo_value} {base_value}".lower()
            if query not in haystack:
                continue

        locomotivas.append(
            {
                "id": row.get("id"),
                "tag": tag_value,
                "modelo": modelo_value,
                "base": base_value,
                "combustivel": combustivel_value,
                "volume_tanque": tanque_value,
                "nivel_atual": nivel_value,
                "nivel_display": f"{nivel_value:.0f}%" if nivel_value is not None else "—",
                "foto_url": None,
            }
        )

    allowed_sort = {"modelo", "tag", "base", "combustivel", "nivel"}
    sort_field = sort_by if sort_by in allowed_sort else "modelo"
    direction = "desc" if sort_dir == "desc" else "asc"
    reverse_sort = direction == "desc"

    def _sort_key(item: dict):
        if sort_field == "nivel":
            nivel = item.get("nivel_atual")
            return -1 if nivel is None else float(nivel)
        value = item.get(sort_field)
        return str(value or "").lower()

    locomotivas.sort(key=_sort_key, reverse=reverse_sort)

    total = len(locomotivas)
    total_pages = max(1, math.ceil(total / max(1, per_page)))
    safe_page = max(1, min(page, total_pages))
    start = (safe_page - 1) * per_page
    end = start + per_page
    page_items = locomotivas[start:end]

    for item in page_items:
        item_id = item.get("id")
        item["foto_url"] = fetch_vehicle_photo(str(item_id)) if item_id else None

    return {
        "items": page_items,
        "total": total,
        "total_pages": total_pages,
        "page": safe_page,
        "sort_by": sort_field,
        "sort_dir": direction,
    }


def fetch_locomotivas_levels() -> list[dict]:
    client = get_supabase_service() or require_supabase()
    try:
        response = (
            client.table("locomotivas")
            .select("id, tag, modelo, base, combustivel, volume_tanque, nivel_atual, exibe_nivel, updated_at, created_at")
            .eq("exibe_nivel", True)
            .order("tag", desc=False)
            .limit(500)
            .execute()
        )
        rows = response.data or []
    except Exception as exc:
        print(f"[WARN] Erro ao consultar locomotivas para painel: {exc}", flush=True)
        return []

    now_utc = datetime.now(timezone.utc)
    now_brt = now_utc.astimezone(BRT_TZ)
    now_brt_display = now_brt.strftime("%d/%m/%Y - %H:%M")
    items: list[dict] = []
    for row in rows:
        nivel_percent = _normalize_level_percentage(_safe_float(row.get("nivel_atual")))
        status = _classify_level_status(nivel_percent)
        is_critical_focus = nivel_percent is not None and nivel_percent < 25
        capacidade = _safe_float(row.get("volume_tanque"))
        nivel_ratio = (nivel_percent / 100.0) if (nivel_percent is not None) else None
        volume_atual = round(capacidade * nivel_ratio, 1) if (capacidade is not None and nivel_ratio is not None) else None
        volume_para_completar = max(0.0, round(capacidade - (capacidade * nivel_ratio), 1)) if (capacidade is not None and nivel_ratio is not None) else None
        litros_disponiveis = math.ceil(volume_para_completar) if volume_para_completar is not None else None
        autonomia_total = None

        updated_dt = _parse_datetime(row.get("updated_at")) or _parse_datetime(row.get("created_at"))
        minutes = None
        status_online = False
        status_label = "offline"
        ultima_diff_display = None
        if updated_dt:
            minutes = max(0.0, round((now_utc - updated_dt).total_seconds() / 60.0, 1))
            if minutes <= 2:
                status_online = True
                status_label = "online"
            ultima_diff_display = f"{minutes:.1f} min"

        loco_id = str(row.get("id") or "")
        base = str(row.get("base") or "").strip()
        modelo = str(row.get("modelo") or "").strip()
        tag = str(row.get("tag") or "").strip()

        items.append(
            {
                "id": row.get("id"),
                "nome": tag or modelo or "Locomotiva",
                "tag": tag,
                "local": base or "Base não informada",
                "modelo": modelo,
                "combustivel": str(row.get("combustivel") or "").strip() or "—",
                "nivel_percent": nivel_percent,
                "nivel_display": f"{nivel_percent:.0f}%" if nivel_percent is not None else "—",
                "nivel_status": status,
                "level_color": (
                    LEVEL_STATUS_COLORS["critical"]
                    if (nivel_percent is not None and nivel_percent < 25)
                    else LEVEL_STATUS_COLORS.get(status, LEVEL_STATUS_COLORS["unknown"])
                ),
                "is_critical_focus": is_critical_focus,
                "autonomia_value": autonomia_total,
                "autonomia_display": f"{autonomia_total:.1f} h" if autonomia_total is not None else None,
                "volume_atual": volume_atual,
                "volume_para_completar": volume_para_completar,
                "litros_disponiveis": litros_disponiveis,
                "maps_url": None,
                "ultima_diff_minutes": minutes,
                "ultima_diff_display": ultima_diff_display,
                "ultima_atualizacao_dt": updated_dt,
                "status_online": status_online,
                "status_label": status_label,
                "brasilia_now_display": now_brt_display,
                "foto_url": fetch_vehicle_photo(loco_id) if loco_id else None,
            }
        )

    return items


def upload_vehicle_photo(veiculo_id: str, photo_file) -> str | None:
    if not veiculo_id or not photo_file or not getattr(photo_file, "filename", ""):
        return None

    filename = secure_filename(photo_file.filename)
    if not filename:
        return None

    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "jpg"
    if ext not in {"jpg", "jpeg", "png", "webp"}:
        raise ValueError("Formato de imagem inválido. Use JPG, PNG ou WEBP.")

    file_bytes = photo_file.read()
    if not file_bytes:
        return None

    content_type = getattr(photo_file, "mimetype", None) or "image/jpeg"
    storage = require_supabase().storage.from_("veiculos")

    delete_vehicle_photos(veiculo_id)

    final_name = f"foto_{uuid.uuid4().hex[:8]}.{ext}"
    upload_path = f"{veiculo_id}/{final_name}"
    storage.upload(upload_path, file_bytes, {"content-type": content_type, "upsert": "true"})
    return storage.get_public_url(upload_path)


def _normalize_areas(raw) -> list[str]:
    """Ensure we always work with a clean list of area strings."""
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(a).strip() for a in raw if str(a).strip()]
    if isinstance(raw, str):
        # Try to parse JSON list, otherwise treat as single value
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return [str(a).strip() for a in parsed if str(a).strip()]
        except Exception:
            pass
        cleaned = raw.strip()
        return [cleaned] if cleaned else []
    return []


def get_authorized_areas(user: dict | None) -> list[str]:
    user = user or {}
    # Retorna apenas a área única do usuário como lista
    if user.get("area"):
        return [user.get("area")]
    return []


def get_primary_area(user: dict | None) -> str | None:
    areas = get_authorized_areas(user)
    if areas:
        return areas[0]
    return (user or {}).get("area")


def apply_area_filter(query, user: dict | None, column: str = "area"):
    areas = get_authorized_areas(user)
    if areas:
        try:
            return query.in_(column, areas)
        except Exception:
            # Fallback: if .in_ not available, filter one by one (no-op on error)
            return query
    if user and user.get("area"):
        return query.eq(column, user["area"])
    return query


def user_can_access_area(user: dict | None, area_value: str | None) -> bool:
    areas = get_authorized_areas(user)
    if not areas:
        return True
    if area_value is None:
        return False
    return area_value in areas


def require_supabase() -> Client:
    global supabase
    if supabase is None:
        # Tenta criar o cliente na primeira chamada usando as variáveis de ambiente.
        if SUPABASE_URL and SUPABASE_ANON_KEY:
            try:
                print(f"[DEBUG] Iniciando create_client com URL: {SUPABASE_URL[:30]}...", flush=True)
                supabase = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
                print(f"[DEBUG] create_client concluído com sucesso", flush=True)
            except Exception as exc:
                print(f"[ERROR] create_client falhou: {exc}", flush=True)
                raise RuntimeError(
                    "Supabase client not configured. Falha ao inicializar o cliente Supabase: %s" % exc
                ) from exc
        else:
            raise RuntimeError(
                "Supabase client not configured. Defina SUPABASE_ANON_KEY em um .env ou variável de ambiente."
            )
    return supabase


def get_supabase_service() -> Client | None:
    """Retorna cliente Supabase com service role (opcional) para operações administrativas"""
    global supabase_service
    if supabase_service is None and SUPABASE_URL and SUPABASE_SERVICE_ROLE:
        try:
            print(f"[DEBUG] Iniciando create_client para service role...", flush=True)
            supabase_service = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE)
            print(f"[DEBUG] Service role client criado com sucesso", flush=True)
        except Exception as exc:
            print(f"[WARN] Não foi possível criar service role client: {exc}", flush=True)
            supabase_service = None
    return supabase_service


def refresh_session_role() -> None:
    user = session.get("user")
    if not user:
        return
    try:
        client = require_supabase()
        profile = (
            client.table("usuarios")
            .select("nome, empresa, role, autorizado, area")
            .eq("id", user["id"])
            .single()
            .execute()
        )
        data = profile.data or {}
        # Preserva role do banco se existir e não for vazio; senão usa fallback baseado em autorizado
        role_from_db = data.get("role")
        if role_from_db and str(role_from_db).strip():
            resolved_role = str(role_from_db).strip()
        else:
            resolved_role = "admin" if data.get("autorizado") else "user"
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
            if role:
                current_role = (user.get("role") or "").strip().lower()
                required_role = (role or "").strip().lower()
                admin_like_roles = {"admin", "administrador", "superadm"}

                if required_role == "admin":
                    if current_role not in admin_like_roles:
                        flash("Acesso não autorizado para este perfil.", "error")
                        return redirect(url_for("home"))
                elif current_role != required_role:
                    flash("Acesso não autorizado para este perfil.", "error")
                    return redirect(url_for("home"))
            return func(*args, **kwargs)

        return wrapper

    return decorator


@app.context_processor
def inject_user():
    return {
        "current_user": session.get("user"),
        "locomotiva_bases": LOCOMOTIVA_BASES,
        "locomotiva_combustiveis": LOCOMOTIVA_COMBUSTIVEIS,
    }


@app.before_request
def log_request():
    user = session.get("user") or {}
    print(
        f"[DEBUG] BEFORE REQUEST path={request.path} endpoint={request.endpoint} user_id={user.get('id')} role={user.get('role')}",
        flush=True,
    )


# Evita que formulários fiquem em cache e reabram ao voltar no navegador
@app.after_request
def add_no_cache_headers(response):
    no_cache_endpoints = {
        "register",
        "login",
        "home",
        "locomotivas",
        "reservatorios",
        "admin_locomotivas",
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
    print("[DEBUG] Acessando rota /home (fuel levels)", flush=True)
    
    # Check if access logging is enabled
    client = get_supabase_service() or require_supabase()
    try:
        controle_rows = (
            client.table("controle")
            .select("valor")
            .eq("controle", "logAcesso")
            .execute()
            .data
            or []
        )
        log_acesso_enabled = controle_rows[0].get("valor") == True if controle_rows else False
        
        if log_acesso_enabled:
            session_user = session.get("user") or {}
            user_email = session_user.get("email") or None
            user_nome = session_user.get("nome") or None
            is_logged = bool(user_email)
            
            log_data = {
                "logado": is_logged
            }
            if is_logged:
                log_data["email"] = user_email
                log_data["nome"] = user_nome
            
            client.table("logAcessos").insert(log_data).execute()
            print(f"[DEBUG] Log de acesso registrado: logado={is_logged}", flush=True)
    except Exception as e:
        print(f"[WARN] Erro ao registrar log de acesso: {e}", flush=True)
    
    fuel_levels = fetch_generator_levels()
    print(f"[DEBUG] Carregados {len(fuel_levels)} geradores", flush=True)
    latest_dt = None
    for item in fuel_levels:
        dt_value = item.get("ultima_atualizacao_dt")
        if not dt_value:
            continue
        if latest_dt is None or dt_value > latest_dt:
            latest_dt = dt_value
    last_refresh = _format_datetime_display(latest_dt)
    print(f"[DEBUG] Última atualização calculada: {last_refresh}", flush=True)

    return render_template(
        "fuel_levels.html",
        fuel_levels=fuel_levels,
        last_refresh=last_refresh,
        active_tab="home",
        active_section="geradores",
    )


@app.route("/locomotivas")
def locomotivas():
    locomotivas_levels = fetch_locomotivas_levels()
    latest_dt = None
    for item in locomotivas_levels:
        dt_value = item.get("ultima_atualizacao_dt")
        if not dt_value:
            continue
        if latest_dt is None or dt_value > latest_dt:
            latest_dt = dt_value

    return render_template(
        "locomotivas.html",
        locomotivas_levels=locomotivas_levels,
        last_refresh=_format_datetime_display(latest_dt),
        active_section="locomotivas",
    )


@app.route("/reservatorios")
def reservatorios():
    return render_template(
        "reservatorios.html",
        active_section="reservatorios",
    )


@app.route("/operacao")
@login_required()
def operacao():
    equipamentos = fetch_operacao_elevadores()
    return render_template(
        "operacao.html",
        equipamentos=equipamentos,
        active_tab="operacao",
    )


@app.route("/api/operacao/equipamentos")
@login_required()
def api_operacao_equipamentos():
    equipamentos = fetch_operacao_elevadores()
    return jsonify({"items": equipamentos})


@app.route("/api/operacao/equipamentos/<string:equipamento_id>/estado", methods=["POST"])
@login_required()
def toggle_operacao_estado(equipamento_id: str):
    client = get_supabase_service() or require_supabase()

    try:
        row = (
            client.table("equipamentos")
            .select("id, estado, ultimaAtualizacao")
            .eq("id", equipamento_id)
            .single()
            .execute()
            .data
        )
    except Exception as exc:
        return jsonify({"success": False, "error": f"Equipamento não encontrado: {exc}"}), 404

    ultima_dt = _parse_datetime((row or {}).get("ultimaAtualizacao"))
    is_online = False
    if ultima_dt:
        is_online = (datetime.now(timezone.utc) - ultima_dt) <= timedelta(minutes=2)
    if not is_online:
        return jsonify({"success": False, "error": "Equipamento offline. Estado não pode ser alterado."}), 400

    payload = request.get_json(silent=True) or {}
    requested_state = payload.get("estado")

    current_state_raw = (row or {}).get("estado")
    if isinstance(current_state_raw, bool):
        current_state = current_state_raw
    elif isinstance(current_state_raw, str):
        current_state = current_state_raw.strip().lower() in {"true", "1", "t", "yes", "y"}
    elif isinstance(current_state_raw, (int, float)):
        current_state = int(current_state_raw) == 1
    else:
        current_state = False

    if isinstance(requested_state, bool):
        new_state = requested_state
    elif isinstance(requested_state, str):
        new_state = requested_state.strip().lower() in {"true", "1", "t", "yes", "y"}
    elif isinstance(requested_state, (int, float)):
        new_state = int(requested_state) == 1
    else:
        new_state = not current_state

    try:
        client.table("equipamentos").update({"estado": new_state}).eq("id", equipamento_id).execute()
        return jsonify(
            {
                "success": True,
                "id": equipamento_id,
                "estado": new_state,
                "estado_label": "ATIVADO" if new_state else "DESATIVADO",
            }
        )
    except Exception as exc:
        return jsonify({"success": False, "error": f"Falha ao atualizar estado: {exc}"}), 500


@app.route("/api/fuel-levels")
def api_fuel_levels():
    fuel_levels = fetch_generator_levels()
    latest_dt = None
    for item in fuel_levels:
        dt_value = item.get("ultima_atualizacao_dt")
        if not dt_value:
            continue
        if latest_dt is None or dt_value > latest_dt:
            latest_dt = dt_value

    payload = []
    for item in fuel_levels:
        payload.append(
            {
                "id": item.get("id"),
                "nome": item.get("nome"),
                "local": item.get("local"),
                "nivel_percent": item.get("nivel_percent"),
                "nivel_display": item.get("nivel_display"),
                "nivel_status": item.get("nivel_status"),
                "level_color": item.get("level_color"),
                "maps_url": item.get("maps_url"),
                "is_critical_focus": item.get("is_critical_focus"),
                "autonomia_value": item.get("autonomia_value"),
                "autonomia_display": item.get("autonomia_display"),
                "volume_tanque": item.get("volume_tanque"),
                "volume_atual": item.get("volume_atual"),
                "volume_para_completar": item.get("volume_para_completar"),
                "litros_disponiveis": item.get("litros_disponiveis"),
                "ultima_atualizacao_display": item.get("ultima_atualizacao_display"),
                "ultima_atualizacao_iso": item.get("ultima_atualizacao_iso"),
                "status_online": item.get("status_online"),
                "status_label": item.get("status_label"),
                "ultima_diff_minutes": item.get("ultima_diff_minutes"),
                "ultima_diff_display": item.get("ultima_diff_display"),
                "brasilia_now_display": item.get("brasilia_now_display"),
            }
        )
    is_authenticated = session.get("user") is not None

    last_refresh = _format_datetime_display(latest_dt)
    brasilia_now = fuel_levels[0].get("brasilia_now_display") if fuel_levels else None
    return jsonify({
        "items": payload,
        "last_refresh": last_refresh,
        "brasilia_now": brasilia_now,
        "is_authenticated": is_authenticated,
    })


@app.route("/api/locomotivas-levels")
def api_locomotivas_levels():
    locomotivas_levels = fetch_locomotivas_levels()
    latest_dt = None
    for item in locomotivas_levels:
        dt_value = item.get("ultima_atualizacao_dt")
        if not dt_value:
            continue
        if latest_dt is None or dt_value > latest_dt:
            latest_dt = dt_value

    payload = []
    for item in locomotivas_levels:
        payload.append(
            {
                "id": item.get("id"),
                "nome": item.get("nome"),
                "tag": item.get("tag"),
                "modelo": item.get("modelo"),
                "local": item.get("local"),
                "nivel_percent": item.get("nivel_percent"),
                "nivel_display": item.get("nivel_display"),
                "nivel_status": item.get("nivel_status"),
                "level_color": item.get("level_color"),
                "maps_url": item.get("maps_url"),
                "is_critical_focus": item.get("is_critical_focus"),
                "litros_disponiveis": item.get("litros_disponiveis"),
                "ultima_atualizacao_display": item.get("ultima_atualizacao_display"),
                "ultima_atualizacao_iso": item.get("ultima_atualizacao_iso"),
                "status_online": item.get("status_online"),
                "status_label": item.get("status_label"),
                "ultima_diff_minutes": item.get("ultima_diff_minutes"),
                "ultima_diff_display": item.get("ultima_diff_display"),
                "brasilia_now_display": item.get("brasilia_now_display"),
            }
        )

    is_authenticated = session.get("user") is not None
    last_refresh = _format_datetime_display(latest_dt)
    brasilia_now = locomotivas_levels[0].get("brasilia_now_display") if locomotivas_levels else None
    return jsonify(
        {
            "items": payload,
            "last_refresh": last_refresh,
            "brasilia_now": brasilia_now,
            "is_authenticated": is_authenticated,
        }
    )


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user"):
        return redirect(url_for("home"))

    if request.method == "POST":
        print("[DEBUG] POST /login iniciado", flush=True)
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not email or not password:
            flash("Informe e-mail e senha.", "error")
            return redirect(url_for("login"))

        client = require_supabase()
        try:
            auth_response = client.auth.sign_in_with_password({"email": email, "password": password})
            user = auth_response.user
            print(f"[DEBUG] Login Supabase ok para {email}", flush=True)
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

        # Preserva role do banco se existir e não for vazio; senão usa fallback baseado em autorizado
        role_from_db = profile_data.get("role")
        if role_from_db and str(role_from_db).strip():
            role = str(role_from_db).strip()
        else:
            role = "admin" if profile_data.get("autorizado") else "user"
        session["user"] = {
            "id": user.id,
            "email": user.email,
            "nome": profile_data.get("nome") or (user.email.split("@")[0] if user.email else "Usuário"),
            "empresa": profile_data.get("empresa"),
            "area": profile_data.get("area"),
            "role": role,
        }
        print(f"[DEBUG] Login concluído para {email}, redirecionando para home", flush=True)
        flash("Bem-vindo!", "success")
        return redirect(url_for("home"))

    return render_template("login.html", active_tab="login")


@app.route("/register", methods=["GET", "POST"])
def register():
    if session.get("user"):
        return redirect(url_for("home"))

    if request.method == "POST":
        print("[DEBUG] POST /register iniciado", flush=True)
        nome = request.form.get("nome", "").strip()
        empresa = request.form.get("empresa", "").strip()
        area = request.form.get("area", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("password_confirm", "")

        required_fields = [
            (nome, "nome completo"),
            (email, "e-mail"),
            (empresa, "empresa"),
            (area, "área"),
            (password, "senha"),
            (confirm, "confirmação da senha"),
        ]
        missing_labels = [label for value, label in required_fields if not value]
        if missing_labels:
            campos = ", ".join(missing_labels)
            flash(f"Preencha todos os campos do cadastro: {campos}.", "error")
            return redirect(url_for("register"))

        if password != confirm:
            flash("As senhas não conferem.", "error")
            return redirect(url_for("register"))

        client = require_supabase()
        try:
            print(f"[DEBUG] Chamando supabase.sign_up para {email}", flush=True)
            signup_response = client.auth.sign_up({"email": email, "password": password})
            user = signup_response.user
            if not user:
                flash("Não foi possível criar o usuário no Supabase.", "error")
                return redirect(url_for("register"))

            # Se houver service role, confirma o e-mail automaticamente para evitar o erro "email not confirmed".
            service_client = get_supabase_service()
            if service_client:
                try:
                    service_client.auth.admin.update_user_by_id(user.id, {"email_confirm": True})
                except Exception:
                    # Se falhar, seguimos, mas o usuário pode precisar confirmar por e-mail.
                    pass

            profile_payload = build_user_profile_payload(
                user_id=user.id,
                nome=nome,
                email=email,
                empresa=empresa,
                area=area,
            )
            print(f"[DEBUG] Gravando perfil na tabela usuarios para {email}", flush=True)
            # Prioriza service role para garantir escrita independente de RLS; fallback para client comum.
            target_client = get_supabase_service() or client
            try:
                target_client.table("usuarios").upsert(profile_payload).execute()
            except Exception as exc:  # pragma: no cover - depende de RLS/permissões
                print(f"[ERROR] Falha ao gravar perfil na tabela usuarios: {exc}", flush=True)
                flash("Erro ao gravar o perfil. Verifique a configuração de SUPABASE_SERVICE_ROLE ou as permissões da tabela usuarios.", "error")
                return redirect(url_for("register"))
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
            "role": "Usuário",
        }
        print(f"[DEBUG] Cadastro concluído para {email}, redirecionando para home", flush=True)
        flash("Cadastro realizado! Bem-vindo.", "success")
        return redirect(url_for("home"))

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


@app.route("/admin/usuarios")
@login_required("admin")
def lista_usuarios():
    client = get_supabase_service() or require_supabase()
    session_user = session.get("user") or {}
    current_role = (session_user.get("role") or "").strip().lower()
    empresa_filter = (session_user.get("empresa") or "").strip()
    area_filter = (session_user.get("area") or "").strip()

    query = client.table("usuarios").select("id, nome, email, empresa, area, autorizado, created_at, role")

    if current_role in {"admin", "administrador"}:
        if empresa_filter:
            query = query.eq("empresa", empresa_filter)
        if area_filter:
            query = query.eq("area", area_filter)

    data = (
        query
        .order("nome", desc=False)
        .limit(300)
        .execute()
        .data
        or []
    )
    def _matches_admin_scope(item: dict) -> bool:
        if current_role not in {"admin", "administrador"}:
            return True
        
        # Administrador não pode ver usuários com role superAdm
        item_role = (item.get("role") or "").strip().lower()
        if item_role == "superadm":
            return False
        
        item_empresa = (item.get("empresa") or "").strip()
        item_area = (item.get("area") or "").strip()
        if empresa_filter and item_empresa.lower() != empresa_filter.lower():
            return False
        if area_filter and item_area.lower() != area_filter.lower():
            return False
        return True

    usuarios = []
    for item in data:
        if not _matches_admin_scope(item):
            continue
        usuarios.append(item)
    return render_template("usuarios_list.html", usuarios=usuarios, areas=REGISTER_AREAS)


@app.route("/admin/locomotivas")
@login_required("admin")
def admin_locomotivas():
    if not _is_superadm_session():
        flash("Acesso não autorizado para este perfil.", "error")
        return redirect(url_for("home"))

    search_term = (request.args.get("q") or "").strip()
    sort_by = (request.args.get("sort_by") or "modelo").strip().lower()
    sort_dir = (request.args.get("sort_dir") or "asc").strip().lower()
    try:
        page = int((request.args.get("page") or "1").strip())
    except ValueError:
        page = 1

    result = fetch_locomotivas_admin(
        search_term=search_term,
        sort_by=sort_by,
        sort_dir=sort_dir,
        page=page,
        per_page=10,
    )

    current_page = result.get("page", 1)
    total_pages = result.get("total_pages", 1)
    page_start = max(1, current_page - 2)
    page_end = min(total_pages, current_page + 2)
    page_numbers = list(range(page_start, page_end + 1))

    return render_template(
        "locomotivas_admin.html",
        locomotivas=result.get("items", []),
        total_locomotivas=result.get("total", 0),
        current_page=current_page,
        total_pages=total_pages,
        page_numbers=page_numbers,
        search_term=search_term,
        sort_by=result.get("sort_by", "modelo"),
        sort_dir=result.get("sort_dir", "asc"),
        combustiveis=LOCOMOTIVA_COMBUSTIVEIS,
        bases=LOCOMOTIVA_BASES,
    )


@app.route("/admin/locomotivas/create", methods=["POST"])
@login_required("admin")
def criar_locomotiva():
    if not _is_superadm_session():
        flash("Acesso não autorizado para este perfil.", "error")
        return redirect(url_for("home"))

    tag = (request.form.get("tag") or "").strip()
    modelo = (request.form.get("modelo") or "").strip()
    base = (request.form.get("base") or "").strip()
    combustivel = (request.form.get("combustivel") or "").strip()
    tanque_raw = (request.form.get("volume_tanque") or "").strip()
    nivel_raw = (request.form.get("nivel_atual") or "0").strip()
    photo_file = request.files.get("foto")

    if not tag or not modelo or not base or not combustivel or not tanque_raw:
        flash("Preencha foto, tag, modelo, base, combustível e volume do tanque.", "error")
        return redirect(url_for("admin_locomotivas"))

    if base not in LOCOMOTIVA_BASE_LABELS:
        flash("Base inválida. Se necessário, cadastre a opção na lista de bases do código.", "error")
        return redirect(url_for("admin_locomotivas"))

    if combustivel not in LOCOMOTIVA_COMBUSTIVEL_LABELS:
        flash("Combustível inválido. Use apenas Diesel S10 ou Diesel S500.", "error")
        return redirect(url_for("admin_locomotivas"))

    if not photo_file or not photo_file.filename:
        flash("A foto da locomotiva é obrigatória.", "error")
        return redirect(url_for("admin_locomotivas"))

    if not tanque_raw.isdigit():
        flash("Volume do tanque deve ser um número inteiro maior que zero.", "error")
        return redirect(url_for("admin_locomotivas"))

    volume_tanque = int(tanque_raw)

    if not nivel_raw.isdigit():
        flash("Nível atual deve ser um número inteiro entre 0 e 100.", "error")
        return redirect(url_for("admin_locomotivas"))

    nivel_atual = int(nivel_raw)

    if volume_tanque <= 0:
        flash("Volume do tanque deve ser maior que zero.", "error")
        return redirect(url_for("admin_locomotivas"))

    if nivel_atual < 0 or nivel_atual > 100:
        flash("Nível atual deve estar entre 0 e 100.", "error")
        return redirect(url_for("admin_locomotivas"))

    payload = {
        "tag": tag,
        "modelo": modelo,
        "base": base,
        "combustivel": combustivel,
        "volume_tanque": volume_tanque,
        "nivel_atual": nivel_atual,
        "exibe_nivel": True,
    }

    client = get_supabase_service() or require_supabase()
    try:
        inserted = client.table("locomotivas").insert(payload).execute().data or []
        created = inserted[0] if inserted else None
        loco_id = str((created or {}).get("id") or "")

        if loco_id and photo_file and photo_file.filename:
            foto_path = upload_vehicle_photo(loco_id, photo_file)
            if foto_path:
                client.table("locomotivas").update({"foto_path": foto_path}).eq("id", loco_id).execute()

        flash("Locomotiva cadastrada com sucesso.", "success")
    except Exception as exc:
        flash(f"Erro ao cadastrar locomotiva: {exc}", "error")

    return redirect(url_for("admin_locomotivas"))


@app.route("/admin/locomotivas/<string:loco_id>/edit", methods=["POST"])
@login_required("admin")
def editar_locomotiva(loco_id: str):
    if not _is_superadm_session():
        flash("Acesso não autorizado para este perfil.", "error")
        return redirect(url_for("home"))

    tag = (request.form.get("tag") or "").strip()
    modelo = (request.form.get("modelo") or "").strip()
    base = (request.form.get("base") or "").strip()
    combustivel = (request.form.get("combustivel") or "").strip()
    tanque_raw = (request.form.get("volume_tanque") or "").strip()
    nivel_raw = (request.form.get("nivel_atual") or "0").strip()

    if not tag or not modelo or not base or not combustivel or not tanque_raw:
        flash("Preencha tag, modelo, base, combustível e volume do tanque.", "error")
        return redirect(url_for("admin_locomotivas"))

    if base not in LOCOMOTIVA_BASE_LABELS:
        flash("Base inválida. Se necessário, cadastre a opção na lista de bases do código.", "error")
        return redirect(url_for("admin_locomotivas"))

    if combustivel not in LOCOMOTIVA_COMBUSTIVEL_LABELS:
        flash("Combustível inválido. Use apenas Diesel S10 ou Diesel S500.", "error")
        return redirect(url_for("admin_locomotivas"))

    if not tanque_raw.isdigit():
        flash("Volume do tanque deve ser um número inteiro maior que zero.", "error")
        return redirect(url_for("admin_locomotivas"))

    volume_tanque = int(tanque_raw)

    if not nivel_raw.isdigit():
        flash("Nível atual deve ser um número inteiro entre 0 e 100.", "error")
        return redirect(url_for("admin_locomotivas"))

    nivel_atual = int(nivel_raw)

    if volume_tanque <= 0:
        flash("Volume do tanque deve ser maior que zero.", "error")
        return redirect(url_for("admin_locomotivas"))

    if nivel_atual < 0 or nivel_atual > 100:
        flash("Nível atual deve estar entre 0 e 100.", "error")
        return redirect(url_for("admin_locomotivas"))

    client = get_supabase_service() or require_supabase()
    try:
        update_payload = {
            "tag": tag,
            "modelo": modelo,
            "base": base,
            "combustivel": combustivel,
            "volume_tanque": volume_tanque,
            "nivel_atual": nivel_atual,
        }
        client.table("locomotivas").update(update_payload).eq("id", loco_id).execute()

        photo_file = request.files.get("foto")
        if photo_file and photo_file.filename:
            foto_path = upload_vehicle_photo(loco_id, photo_file)
            if foto_path:
                client.table("locomotivas").update({"foto_path": foto_path}).eq("id", loco_id).execute()

        flash("Locomotiva atualizada com sucesso.", "success")
    except Exception as exc:
        flash(f"Erro ao editar locomotiva: {exc}", "error")

    return redirect(url_for("admin_locomotivas"))


@app.route("/admin/locomotivas/<string:loco_id>/delete", methods=["POST"])
@login_required("admin")
def deletar_locomotiva(loco_id: str):
    if not _is_superadm_session():
        flash("Acesso não autorizado para este perfil.", "error")
        return redirect(url_for("home"))

    client = get_supabase_service() or require_supabase()
    try:
        client.table("locomotivas").delete().eq("id", loco_id).execute()
        delete_vehicle_photos(loco_id)
        flash("Locomotiva excluída com sucesso.", "success")
    except Exception as exc:
        flash(f"Erro ao excluir locomotiva: {exc}", "error")

    return redirect(url_for("admin_locomotivas"))


@app.route("/admin/numeros")
@login_required("admin")
def dashboard_numeros():
    session_user = session.get("user") or {}
    current_role = (session_user.get("role") or "").strip().lower()
    if current_role != "superadm":
        flash("Acesso não autorizado para este perfil.", "error")
        return redirect(url_for("home"))

    client = get_supabase_service() or require_supabase()

    # Fetch control value for logAcesso
    log_acesso_enabled = False
    try:
        controle_rows = (
            client.table("controle")
            .select("valor")
            .eq("controle", "logAcesso")
            .execute()
            .data
            or []
        )
        if controle_rows:
            log_acesso_enabled = controle_rows[0].get("valor") == True
    except Exception as e:
        print(f"[WARN] Erro ao buscar controle logAcesso: {e}", flush=True)

    usuarios_rows = (
        client.table("usuarios")
        .select("id, area")
        .order("id", desc=False)
        .limit(5000)
        .execute()
        .data
        or []
    )

    total_usuarios = len(usuarios_rows)
    usuarios_por_area: dict[str, int] = {}
    for user_row in usuarios_rows:
        area_value = (user_row.get("area") or "Sem área").strip() or "Sem área"
        usuarios_por_area[area_value] = usuarios_por_area.get(area_value, 0) + 1

    area_labels = sorted(usuarios_por_area.keys(), key=lambda value: value.lower())
    area_values = [usuarios_por_area[label] for label in area_labels]

    logs_rows = (
        client.table("logAcessos")
        .select("created_at")
        .order("created_at", desc=False)
        .limit(10000)
        .execute()
        .data
        or []
    )

    acessos_por_dia: dict[str, int] = {}
    for log_row in logs_rows:
        created_at = log_row.get("created_at")
        dt_value = _parse_datetime(created_at)
        if not dt_value:
            continue
        day_key = dt_value.astimezone(BRT_TZ).strftime("%Y-%m-%d")
        acessos_por_dia[day_key] = acessos_por_dia.get(day_key, 0) + 1

    day_keys_sorted = sorted(acessos_por_dia.keys())
    acesso_labels = []
    acesso_values = []
    for day_key in day_keys_sorted:
        day_dt = datetime.strptime(day_key, "%Y-%m-%d")
        acesso_labels.append(day_dt.strftime("%d/%m"))
        acesso_values.append(acessos_por_dia[day_key])

    return render_template(
        "dashboard_numeros.html",
        total_usuarios=total_usuarios,
        area_labels=area_labels,
        area_values=area_values,
        total_acessos=sum(acesso_values),
        acesso_labels=acesso_labels,
        acesso_values=acesso_values,
        log_acesso_enabled=log_acesso_enabled,
    )


@app.route("/api/toggle-log-acesso", methods=["POST"])
@login_required("admin")
def toggle_log_acesso():
    """Toggle the logAcesso control value"""
    session_user = session.get("user") or {}
    current_role = (session_user.get("role") or "").strip().lower()
    if current_role != "superadm":
        return jsonify({"success": False, "error": "Acesso não autorizado"}), 403

    try:
        data = request.get_json() or {}
        enabled = data.get("enabled", False)
        
        client = get_supabase_service() or require_supabase()
        
        # Check if control record exists
        controle_rows = (
            client.table("controle")
            .select("id")
            .eq("controle", "logAcesso")
            .execute()
            .data
            or []
        )
        
        if controle_rows:
            # Update existing record
            client.table("controle").update({"valor": enabled}).eq("controle", "logAcesso").execute()
        else:
            # Insert new record
            client.table("controle").insert({"controle": "logAcesso", "valor": enabled}).execute()
        
        print(f"[DEBUG] Log de acesso {'ativado' if enabled else 'desativado'}", flush=True)
        return jsonify({"success": True, "enabled": enabled}), 200
        
    except Exception as e:
        print(f"[ERROR] Erro ao atualizar controle logAcesso: {e}", flush=True)
        return jsonify({"success": False, "error": str(e)}), 500


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
        role = (payload.get("role") or "").strip()
        
        if not nome:
            return {"error": "Nome é obrigatório"}, 400
        
        current_user = session.get("user") or {}
        current_role = (current_user.get("role") or "").strip().lower()
        
        update_payload = {
            "nome": nome,
        }

        # Apenas superadm pode editar empresa e área
        if current_role == "superadm":
            if empresa:
                update_payload["empresa"] = empresa
            if area:
                update_payload["area"] = area

        # Administrador e superadm podem editar role
        if current_role in {"superadm", "admin", "administrador"} and role:
            # Administrador só pode atribuir Usuário ou Administrador
            if current_role in {"admin", "administrador"}:
                if role not in {"Usuário", "Administrador"}:
                    return {"error": "Role inválido"}, 400
            # superAdm pode atribuir qualquer role incluindo superAdm
            elif current_role == "superadm":
                if role not in {"Usuário", "Administrador", "superAdm"}:
                    return {"error": "Role inválido"}, 400
            update_payload["role"] = role

        client.table("usuarios").update(update_payload).eq("id", user_id).execute()
        
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
        service_client = get_supabase_service()
        if service_client:
            try:
                service_client.auth.admin.delete_user(user_id)
            except Exception:
                pass  # Se falhar, continua de qualquer forma
        
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


@app.errorhandler(404)
def not_found(_):
    return render_template("404.html"), 404


@app.errorhandler(500)
def server_error(error):
    return render_template("500.html", error=error), 500


if __name__ == "__main__":
    debug_mode = os.getenv("FLASK_DEBUG", "0") == "1"
    print("=" * 60)
    print("TRIVIA MONITORA - TRIVIA TRENS")
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
