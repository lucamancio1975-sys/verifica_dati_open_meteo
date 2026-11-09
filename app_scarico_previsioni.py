import os
import time
import base64
import requests
import numpy as np
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

# ==========================================
# CONFIGURAZIONE PAGINA E STILE STREAMLIT MOBILE-FIRST
# ==========================================
st.set_page_config(
    page_title="AgroMeteo Pomodoro - Previsioni Orarie VPD",
    page_icon="🍅",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
    .stApp {
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
        background-color: #f4f7f6;
    }
    .header-card {
        background: linear-gradient(135deg, #b51717 0%, #1b4965 100%);
        padding: 20px;
        border-radius: 14px;
        color: white;
        margin-bottom: 20px;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.12);
        text-align: center;
    }
    .header-card h1 {
        margin: 0;
        font-size: 1.8rem;
        font-weight: 700;
        color: #ffffff;
    }
    .header-card p {
        margin-top: 6px;
        margin-bottom: 0;
        font-size: 0.95rem;
        color: #f1faee;
    }
    .info-card {
        background-color: #ffffff;
        border-left: 5px solid #b51717;
        padding: 14px 18px;
        border-radius: 10px;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
        margin-bottom: 16px;
        font-size: 0.95rem;
    }
    .stButton > button {
        background: linear-gradient(135deg, #2a9d8f 0%, #264653 100%);
        color: white;
        border: none;
        font-size: 1.15rem;
        font-weight: 600;
        padding: 14px 20px;
        border-radius: 10px;
        transition: all 0.25s ease;
        box-shadow: 0 4px 10px rgba(42, 157, 143, 0.3);
        width: 100%;
        margin-top: 5px;
        margin-bottom: 15px;
    }
    .stButton > button:hover {
        background: linear-gradient(135deg, #264653 0%, #1d3557 100%);
        box-shadow: 0 6px 14px rgba(42, 157, 143, 0.4);
        transform: translateY(-2px);
    }
    .stDataFrame {
        border-radius: 10px;
        overflow: hidden;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 1. CONFIGURAZIONE CENTRALINE POMODORO (WGS84)
# ==========================================
STAZIONI = {
    "Braccagni": {
        "codice": "TOS11000008",
        "nome_slug": "braccagni",
        "lat": 42.931,
        "lon": 11.080,
        "csv_filename": "TOS11000008_braccagni.csv"
    },
    "Capalbio": {
        "codice": "TOS11000006",
        "nome_slug": "capalbio",
        "lat": 42.405,
        "lon": 11.392,
        "csv_filename": "TOS11000006_capalbio.csv"
    },
    "Cesa": {
        "codice": "TOS11000037",
        "nome_slug": "cesa",
        "lat": 43.308,
        "lon": 11.825,
        "csv_filename": "TOS11000037_cesa.csv"
    },
    "Casotto dei Pescatori": {
        "codice": "TOS11000013",
        "nome_slug": "casotto_dei_pescatori",
        "lat": 42.769,
        "lon": 11.016,
        "csv_filename": "TOS11000013_casotto_dei_pescatori.csv"
    },
    "Rispescia": {
        "codice": "TOS11000005",
        "nome_slug": "rispescia",
        "lat": 42.706,
        "lon": 11.145,
        "csv_filename": "TOS11000005_rispescia.csv"
    },
    "San Donato": {
        "codice": "TOS03003099",
        "nome_slug": "san_donato",
        "lat": 42.554,
        "lon": 11.237,
        "csv_filename": "TOS03003099_san_donato.csv"
    }
}

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
GITHUB_DATA_FOLDER = "data"

CSV_COLUMNS = [
    "stazione",
    "codice_stazione",
    "lat",
    "lon",
    "data_run",
    "data_previsione",
    "ora",
    "data_ora",
    "anticipo_giorni",
    "temp_c",
    "rh_pct",
    "vpd_kpa"
]

# ==========================================
# 2. FUNZIONI DI GESTIONE ARCHIVIO DATA/ E GITHUB
# ==========================================
def ensure_data_dir():
    """Crea la cartella locale data/ se non esiste."""
    os.makedirs(DATA_DIR, exist_ok=True)

def load_local_csv(csv_filename):
    """Carica il file CSV orario della stazione dalla cartella data/."""
    ensure_data_dir()
    filepath = os.path.join(DATA_DIR, csv_filename)
    if os.path.exists(filepath):
        try:
            df = pd.read_csv(filepath)
            return df
        except Exception:
            pass
    return pd.DataFrame(columns=CSV_COLUMNS)

def save_local_csv(df, csv_filename):
    """Salva il DataFrame nel file CSV locale dentro data/."""
    ensure_data_dir()
    filepath = os.path.join(DATA_DIR, csv_filename)
    df.to_csv(filepath, index=False, encoding="utf-8")
    return filepath

def get_github_secrets():
    """Restituisce (token, repo, branch) se presenti nei secrets di Streamlit."""
    try:
        if "GITHUB_TOKEN" in st.secrets and "GITHUB_REPO" in st.secrets:
            token = st.secrets["GITHUB_TOKEN"]
            repo = st.secrets["GITHUB_REPO"]
            branch = st.secrets.get("GITHUB_BRANCH", "main")
            return token, repo, branch
    except Exception:
        pass
    return None, None, None

def sync_github_csv(csv_filename, df):
    """
    Sincronizza il file CSV della singola stazione nella cartella data/ del repository GitHub.
    """
    token, repo, branch = get_github_secrets()
    if not token or not repo:
        return False, "Token GitHub o Nome Repository non configurati nei secret."

    repo_path = f"{GITHUB_DATA_FOLDER}/{csv_filename}"
    url = f"https://api.github.com/repos/{repo}/contents/{repo_path}"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }

    sha = None
    try:
        get_res = requests.get(url, headers=headers, params={"ref": branch}, timeout=10)
        if get_res.status_code == 200:
            sha = get_res.json().get("sha")
    except Exception as e:
        return False, f"Impossibile verificare il file su GitHub: {e}"

    csv_str = df.to_csv(index=False, encoding="utf-8")
    content_b64 = base64.b64encode(csv_str.encode("utf-8")).decode("utf-8")

    payload = {
        "message": f"🤖 Auto-update {repo_path} da Streamlit Run",
        "content": content_b64,
        "branch": branch
    }
    if sha:
        payload["sha"] = sha

    try:
        put_res = requests.put(url, headers=headers, json=payload, timeout=15)
        if put_res.status_code in [200, 201]:
            return True, f"Sincronizzato su GitHub ({repo_path})"
        else:
            return False, f"GitHub API Errore ({put_res.status_code}): {put_res.text}"
    except Exception as e:
        return False, f"Errore durante l'invio su GitHub API: {e}"

# ==========================================
# 3. PROTOCOLLO DI SCARICO OPEN-METEO & CALCOLO VPD TETENS ORARIO
# ==========================================
def calcola_vpd_tetens(temp_c, rh_pct):
    """
    Calcola il VPD (kPa) secondo l'Equazione di Tetens:
    es(T) = 0.61078 * exp((17.27 * T) / (T + 237.3))
    ea    = es(T) * (RH / 100)
    VPD   = es(T) - ea
    """
    e_s = 0.61078 * np.exp((17.27 * temp_c) / (temp_c + 237.3))
    e_a = e_s * (rh_pct / 100.0)
    return e_s - e_a

def fetch_open_meteo_raw(lat, lon, retries=3):
    """
    Scarica i dati orari dai due modelli scelti da protocollo (icon_eu, ecmwf_ifs025)
    per il giorno corrente D+0 (dalle 00:00 alle 23:00, incluse le ore 00:00-06:00 già trascorse),
    il giorno successivo D+1 e il giorno dopo ancora D+2.
    """
    url = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={lat}&longitude={lon}&"
        f"hourly=temperature_2m,relative_humidity_2m&"
        f"models=icon_eu,ecmwf_ifs025&"
        f"timezone=Europe%2FRome&forecast_days=3"
    )
    for attempt in range(retries):
        try:
            res = requests.get(url, timeout=15)
            res.raise_for_status()
            return res.json()
        except Exception as e:
            if attempt == retries - 1:
                raise e
            time.sleep(1.5)

def process_station_forecast(stazione_nome, config, date_run_custom=None):
    """
    Scarica ed elabora i dati orari per una stazione (Run giornaliera ore 07:00):
    1. Media ensemble oraria tra ICON-EU ed ECMWF IFS025 per Temperatura e Umidità Relativa.
    2. Calcolo del VPD orario (kPa) tramite Equazione di Tetens sull'ensemble.
    3. Estrazione delle 24 ore (00:00 - 23:00) per:
       - D+0 (anticipo_giorni=0): ore 00:00-06:00 già trascorse + ore 07:00-23:00 del giorno di run
       - D+1 (anticipo_giorni=1): 24 ore del giorno successivo
       - D+2 (anticipo_giorni=2): 24 ore di due giorni dopo
    """
    raw_data = fetch_open_meteo_raw(config["lat"], config["lon"])
    hourly = raw_data.get("hourly", {})

    times = hourly.get("time", [])
    t_icon = hourly.get("temperature_2m_icon_eu", [])
    rh_icon = hourly.get("relative_humidity_2m_icon_eu", [])
    t_ecmwf = hourly.get("temperature_2m_ecmwf_ifs025", [])
    rh_ecmwf = hourly.get("relative_humidity_2m_ecmwf_ifs025", [])

    if not (times and t_icon and rh_icon and t_ecmwf and rh_ecmwf):
        raise ValueError(f"Dati API Open-Meteo incompleti per {stazione_nome} ({config['codice']})")

    df_all = pd.DataFrame({
        "time_raw": times,
        "temp_icon_eu": pd.to_numeric(t_icon, errors="coerce"),
        "rh_icon_eu": pd.to_numeric(rh_icon, errors="coerce"),
        "temp_ecmwf": pd.to_numeric(t_ecmwf, errors="coerce"),
        "rh_ecmwf": pd.to_numeric(rh_ecmwf, errors="coerce")
    })

    dt_series = pd.to_datetime(df_all["time_raw"])
    df_all["date_obj"] = dt_series.dt.date
    df_all["data_previsione"] = dt_series.dt.strftime("%Y-%m-%d")
    df_all["ora"] = dt_series.dt.hour
    df_all["data_ora"] = dt_series.dt.strftime("%Y-%m-%d %H:%M")

    # Media ensemble dei due modelli previsionali (ICON-EU + ECMWF IFS025)
    t_ens = (df_all["temp_icon_eu"] + df_all["temp_ecmwf"]) / 2.0
    rh_ens = (df_all["rh_icon_eu"] + df_all["rh_ecmwf"]) / 2.0
    df_all["temp_c"] = t_ens.round(2)
    df_all["rh_pct"] = rh_ens.round(2)

    # VPD orario secondo Equazione di Tetens (in kPa)
    df_all["vpd_kpa"] = calcola_vpd_tetens(t_ens, rh_ens).round(4)

    # Determinazione data della Run (D+0)
    run_date = date_run_custom if date_run_custom else dt_series.dt.date.min()
    run_date_str = run_date.strftime("%Y-%m-%d")

    giorno_d0 = run_date
    giorno_d1 = run_date + timedelta(days=1)
    giorno_d2 = run_date + timedelta(days=2)

    frames_estratti = []
    for g_target, anticipo in [(giorno_d0, 0), (giorno_d1, 1), (giorno_d2, 2)]:
        df_sub = df_all[df_all["date_obj"] == g_target].copy()
        if not df_sub.empty:
            df_sub["stazione"] = stazione_nome
            df_sub["codice_stazione"] = config["codice"]
            df_sub["lat"] = config["lat"]
            df_sub["lon"] = config["lon"]
            df_sub["data_run"] = run_date_str
            df_sub["anticipo_giorni"] = anticipo
            frames_estratti.append(df_sub[CSV_COLUMNS])

    if frames_estratti:
        df_hourly_d0_d1_d2 = pd.concat(frames_estratti, ignore_index=True)
    else:
        df_hourly_d0_d1_d2 = pd.DataFrame(columns=CSV_COLUMNS)

    return df_all, df_hourly_d0_d1_d2

def merge_and_replace_fresher(df_old, df_new):
    """
    Inserisce i dati della nuova run nell'archivio e SOSTITUISCE automaticamente
    le ore già presenti da run precedenti (es. vecchi D+2 o D+1) con i dati più freschi
    e precisi della run giornaliera (keep='last' su codice_stazione, data_previsione, ora).
    """
    if df_old.empty:
        df_combined = df_new.copy()
    else:
        df_combined = pd.concat([df_old, df_new], ignore_index=True)

    df_combined["data_run"] = df_combined["data_run"].astype(str)
    df_combined["data_previsione"] = df_combined["data_previsione"].astype(str)
    df_combined["ora"] = df_combined["ora"].astype(int)
    df_combined["anticipo_giorni"] = df_combined["anticipo_giorni"].astype(int)

    # Sostituzione delle ore già presenti con i dati più freschi dell'ultima run (keep="last")
    df_combined = df_combined.drop_duplicates(
        subset=["codice_stazione", "data_previsione", "ora"],
        keep="last"
    )

    df_combined = df_combined.sort_values(
        by=["data_previsione", "ora"],
        ascending=[True, True]
    ).reset_index(drop=True)

    return df_combined

def update_station_database(stazione_nome, config, df_new_hourly, sync_github=True):
    """
    Aggiorna il file CSV in data/<codice>_<nome>.csv sovrascrivendo le ore già presenti
    con quelle più fresche della run corrente e (opzionalmente) sincronizza su GitHub.
    """
    csv_name = config["csv_filename"]
    df_old = load_local_csv(csv_name)
    n_old = len(df_old)

    df_combined = merge_and_replace_fresher(df_old, df_new_hourly)
    n_new_total = len(df_combined)
    n_replaced = (n_old + len(df_new_hourly)) - n_new_total

    local_path = save_local_csv(df_combined, csv_name)

    if sync_github:
        gh_success, gh_msg = sync_github_csv(csv_name, df_combined)
    else:
        gh_success, gh_msg = False, "Sincronizzazione GitHub disattivata."

    return df_combined, local_path, gh_success, gh_msg, n_replaced

# ==========================================
# 4. INTERFACCIA UTENTE STREAMLIT (UI)
# ==========================================
def main():
    st.markdown("""
    <div class="header-card">
        <h1>🍅 AgroMeteo Centraline Pomodoro</h1>
        <p>Run Giornaliera Ore 07:00 • D+0 (00-23), D+1 e D+2 • Ensemble ICON-EU + ECMWF • Sostituzione Dati Freschi</p>
    </div>
    """, unsafe_allow_html=True)

    gh_token, gh_repo, gh_branch = get_github_secrets()
    gh_configured = bool(gh_token and gh_repo)

    st.sidebar.header("⚙️ Pannello di Controllo")
    stazioni_list_md = "\n".join(
        [f"• **{nome}** (`{cfg['codice']}`): {cfg['lat']}°N, {cfg['lon']}°E" for nome, cfg in STAZIONI.items()]
    )
    st.sidebar.info(
        f"**6 Centraline Monitorate**:\n{stazioni_list_md}\n\n"
        f"**Modelli**: ICON-EU + ECMWF IFS025 (Media)\n"
        f"**Finestra Scarico**: D+0 (00-23), D+1, D+2 (72 ore/run)\n"
        f"**Aggiornamento**: Sovrascrittura ore esistenti con dati più freschi\n"
        f"**Cartella Archivio**: `data/<codice>_<nome>.csv`\n"
        f"**GitHub Sync**: {'✅ Attiva (' + str(gh_repo) + ')' if gh_configured else '⚠️ Solo Locale'}"
    )

    st.markdown("""
    <div class="info-card">
        📲 <strong>Workflow Run Mattutina (Ore 07:00):</strong> Scarica per le 6 centraline i dati orari del giorno corrente <strong>D+0</strong> (dalle <code>00:00</code> alle <code>06:00</code> già trascorse + previsione fino alle <code>23:00</code>), di domani (<strong>D+1</strong>) e dopodomani (<strong>D+2</strong>).<br>
        🔄 <strong>Sostituzione Intelligente:</strong> Le ore già presenti in archivio da run precedenti (es. vecchi D+2 e D+1) vengono automaticamente <strong>sovrascritte con i dati più freschi e precisi</strong> dell'ultima run.
    </div>
    """, unsafe_allow_html=True)

    col_btn, col_opt = st.columns([3, 1])
    with col_opt:
        sync_gh_toggle = st.checkbox(
            "Sincronizza su GitHub (`data/`)",
            value=gh_configured,
            disabled=not gh_configured,
            help="Se attivo e i Secrets sono configurati, invia i CSV aggiornati nella cartella data/ del repository GitHub."
        )
    with col_btn:
        btn_run = st.button("🚀 ESEGUI RUN GIORNALIERA (D+0, D+1, D+2 - 6 CENTRALINE)", use_container_width=True)

    if btn_run:
        with st.spinner("⏳ Scarico 72 ore (D+0, D+1, D+2), calcolo VPD Tetens e sostituzione ore con dati più freschi..."):
            esiti = {}
            for st_nome, cfg in STAZIONI.items():
                try:
                    _, df_new_hourly = process_station_forecast(st_nome, cfg)
                    df_updated, local_p, gh_ok, gh_msg, n_rep = update_station_database(
                        st_nome, cfg, df_new_hourly, sync_github=sync_gh_toggle
                    )
                    esiti[st_nome] = {
                        "codice": cfg["codice"],
                        "csv_filename": cfg["csv_filename"],
                        "df_new": df_new_hourly,
                        "df_db": df_updated,
                        "local_path": local_p,
                        "gh_ok": gh_ok,
                        "gh_msg": gh_msg,
                        "n_replaced": n_rep
                    }
                except Exception as e:
                    st.error(f"❌ Errore durante l'elaborazione per **{st_nome} ({cfg['codice']})**: {e}")

        if esiti:
            st.success(f"✅ Run completata per {len(esiti)}/6 centraline! (72 ore estratte per stazione: 24h D+0 + 24h D+1 + 24h D+2)")
            cols_summary = st.columns(3)
            for idx, (st_nome, res) in enumerate(esiti.items()):
                with cols_summary[idx % 3]:
                    df_n = res["df_new"]
                    vpd_d0 = df_n[df_n["anticipo_giorni"] == 0]["vpd_kpa"].mean()
                    vpd_d1 = df_n[df_n["anticipo_giorni"] == 1]["vpd_kpa"].mean()
                    vpd_d2 = df_n[df_n["anticipo_giorni"] == 2]["vpd_kpa"].mean()
                    st.metric(
                        label=f"📍 {st_nome} ({res['codice']})",
                        value=f"D+0: {vpd_d0:.3f} kPa",
                        delta=f"D+1: {vpd_d1:.3f} | D+2: {vpd_d2:.3f} kPa",
                        delta_color="off"
                    )
                    st.caption(
                        f"🔄 Ore aggiornate/sostituite: **{res['n_replaced']}** • Totale archivio: **{len(res['df_db'])}** ore\n\n"
                        + (f"🟢 {res['gh_msg']}" if res["gh_ok"] else f"💾 Locale: `data/{res['csv_filename']}`")
                    )

    st.markdown("---")

    # SEZIONE TAB DI CONSULTAZIONE E ANALISI ORARIA
    tab_hourly, tab_charts, tab_window, tab_stations = st.tabs([
        "🗃️ Archivio CSV Orario (data/)",
        "📈 Curve Orarie VPD (Da Ora X in poi)",
        "⏱️ Sintesi per Fascia Oraria",
        "🗺️ Anagrafica Centraline & GitHub"
    ])

    # TAB 1: ARCHIVIO CSV ORARIO
    with tab_hourly:
        st.subheader("📊 Archivio Dati Orari Consolidati per Stazione (`data/<codice>_<nome>.csv`)")

        col_sel1, col_sel2, col_sel3 = st.columns([2, 1, 1])
        with col_sel1:
            st_scelta = st.selectbox(
                "Seleziona Centralina",
                list(STAZIONI.keys()),
                format_func=lambda k: f"{k} ({STAZIONI[k]['codice']}) - {STAZIONI[k]['csv_filename']}"
            )
        cfg_scelta = STAZIONI[st_scelta]
        df_curr = load_local_csv(cfg_scelta["csv_filename"])

        with col_sel2:
            ora_inizio_tab = st.slider(
                "Filtra da ora in poi (00:00 - 23:00)",
                min_value=0,
                max_value=23,
                value=0,
                step=1,
                help="Utile per ispezionare e predire il VPD orario da una certa ora del giorno in poi."
            )
        with col_sel3:
            anticipo_filtro = st.selectbox(
                "Filtro Orizzonte",
                options=[
                    "Tutti (Consolidati D+0, D+1, D+2)",
                    "Solo D+0 (Giorno Run / Consolidato)",
                    "Solo D+1 (Previsione +1g)",
                    "Solo D+2 (Previsione +2g)"
                ]
            )

        if df_curr.empty:
            st.info(f"Nessun dato archiviato in `data/{cfg_scelta['csv_filename']}`. Premi il pulsante di Run in alto.")
        else:
            df_view = df_curr[df_curr["ora"] >= ora_inizio_tab].copy()
            if anticipo_filtro == "Solo D+0 (Giorno Run / Consolidato)":
                df_view = df_view[df_view["anticipo_giorni"] == 0]
            elif anticipo_filtro == "Solo D+1 (Previsione +1g)":
                df_view = df_view[df_view["anticipo_giorni"] == 1]
            elif anticipo_filtro == "Solo D+2 (Previsione +2g)":
                df_view = df_view[df_view["anticipo_giorni"] == 2]

            st.caption(
                f"File: `data/{cfg_scelta['csv_filename']}` • Righe visualizzate: **{len(df_view)}** su **{len(df_curr)}** totali "
                f"(Fascia oraria: `{ora_inizio_tab:02d}:00 - 23:00`)"
            )
            st.dataframe(df_view, use_container_width=True, height=420)

            col_dl1, col_dl2 = st.columns(2)
            with col_dl1:
                csv_full_bytes = df_curr.to_csv(index=False, encoding="utf-8").encode("utf-8")
                st.download_button(
                    label=f"📥 Scarica CSV Completo ({cfg_scelta['csv_filename']})",
                    data=csv_full_bytes,
                    file_name=cfg_scelta["csv_filename"],
                    mime="text/csv",
                    use_container_width=True
                )
            with col_dl2:
                csv_filt_bytes = df_view.to_csv(index=False, encoding="utf-8").encode("utf-8")
                st.download_button(
                    label=f"📥 Scarica Vista Filtrata (da ore {ora_inizio_tab:02d}:00)",
                    data=csv_filt_bytes,
                    file_name=f"filtrato_{ora_inizio_tab:02d}h_{cfg_scelta['csv_filename']}",
                    mime="text/csv",
                    use_container_width=True
                )

    # TAB 2: GRAFICI CURVE ORARIE VPD
    with tab_charts:
        st.subheader("📈 Andamento Orario VPD, Temperatura e Umidità Relativa (D+0, D+1, D+2)")

        c_g1, c_g2, c_g3 = st.columns([2, 1, 1])
        with c_g1:
            st_graf = st.selectbox(
                "Seleziona Centralina",
                list(STAZIONI.keys()),
                key="graf_stazione",
                format_func=lambda k: f"{k} ({STAZIONI[k]['codice']})"
            )
        cfg_graf = STAZIONI[st_graf]
        df_graf = load_local_csv(cfg_graf["csv_filename"])

        if df_graf.empty:
            st.info("Nessun dato disponibile per generare i grafici. Esegui prima una Run.")
        else:
            date_prev_disponibili = sorted(df_graf["data_previsione"].astype(str).unique(), reverse=True)
            with c_g2:
                data_prev_sel = st.selectbox(
                    "Data Target",
                    options=["Tutte le date (Serie Continua)"] + date_prev_disponibili
                )
            with c_g3:
                ora_start_graf = st.slider(
                    "Da ora in poi (Grafico)",
                    min_value=0,
                    max_value=23,
                    value=0,
                    key="ora_graf"
                )

            df_plot = df_graf[df_graf["ora"] >= ora_start_graf].copy()
            if data_prev_sel != "Tutte le date (Serie Continua)":
                df_plot = df_plot[df_plot["data_previsione"].astype(str) == data_prev_sel]

            df_plot["Orizzonte Dato"] = df_plot["anticipo_giorni"].map({
                0: "D+0 (Giorno Run / Consolidato)",
                1: "D+1 (Previsione +1g)",
                2: "D+2 (Previsione +2g)"
            })
            x_col = "ora" if data_prev_sel != "Tutte le date (Serie Continua)" else "data_ora"

            fig_vpd = px.line(
                df_plot,
                x=x_col,
                y="vpd_kpa",
                color="Orizzonte Dato",
                markers=True,
                hover_data=["data_run", "data_previsione", "ora", "temp_c", "rh_pct"],
                labels={
                    "ora": "Ora del Giorno (0-23)",
                    "data_ora": "Data e Ora",
                    "vpd_kpa": "VPD Orario Tetens (kPa)"
                },
                title=f"Curva VPD Orario (kPa) - {st_graf} ({cfg_graf['codice']}) [Ore {ora_start_graf:02d}:00 - 23:00]"
            )
            fig_vpd.update_layout(template="plotly_white", hovermode="x unified")
            st.plotly_chart(fig_vpd, use_container_width=True)

            col_t, col_rh = st.columns(2)
            with col_t:
                fig_t = px.line(
                    df_plot,
                    x=x_col,
                    y="temp_c",
                    color="Orizzonte Dato",
                    markers=True,
                    labels={"temp_c": "Temperatura Ensemble (°C)", "ora": "Ora", "data_ora": "Data/Ora"},
                    title="Temperatura Oraria Ensemble ICON-EU + ECMWF (°C)"
                )
                fig_t.update_layout(template="plotly_white", hovermode="x unified")
                st.plotly_chart(fig_t, use_container_width=True)

            with col_rh:
                fig_rh = px.line(
                    df_plot,
                    x=x_col,
                    y="rh_pct",
                    color="Orizzonte Dato",
                    markers=True,
                    labels={"rh_pct": "Umidità Relativa Ensemble (%)", "ora": "Ora", "data_ora": "Data/Ora"},
                    title="Umidità Relativa Oraria Ensemble ICON-EU + ECMWF (%)"
                )
                fig_rh.update_layout(template="plotly_white", hovermode="x unified")
                st.plotly_chart(fig_rh, use_container_width=True)

    # TAB 3: SINTESI PER FASCIA ORARIA (ES. DA UNA CERTA ORA IN POI)
    with tab_window:
        st.subheader("⏱️ Calcolo Riepilogativo VPD da una Certa Ora in Poi")
        st.write(
            "Seleziona l'intervallo orario di interesse (es. dalle ore **07:00** o **08:00** fino alle **23:00**) "
            "per visualizzare le statistiche giornaliere di VPD, Temperatura e Umidità Relativa su D+0, D+1 e D+2."
        )

        cw1, cw2 = st.columns([2, 2])
        with cw1:
            st_win = st.selectbox(
                "Centralina",
                list(STAZIONI.keys()),
                key="win_stazione",
                format_func=lambda k: f"{k} ({STAZIONI[k]['codice']})"
            )
        with cw2:
            fascia_ore = st.slider(
                "Seleziona Fascia Oraria di Analisi",
                min_value=0,
                max_value=23,
                value=(7, 23),
                step=1
            )

        df_win_raw = load_local_csv(STAZIONI[st_win]["csv_filename"])
        if df_win_raw.empty:
            st.info("Archivio vuoto per questa stazione.")
        else:
            h_min, h_max = fascia_ore
            df_w = df_win_raw[(df_win_raw["ora"] >= h_min) & (df_win_raw["ora"] <= h_max)].copy()
            df_agg = (
                df_w.groupby(["stazione", "codice_stazione", "data_run", "data_previsione", "anticipo_giorni"], as_index=False)
                .agg(
                    ore_considerate=("ora", "count"),
                    temp_media_fascia=("temp_c", lambda x: round(x.mean(), 2)),
                    rh_media_fascia=("rh_pct", lambda x: round(x.mean(), 2)),
                    vpd_medio_fascia_kpa=("vpd_kpa", lambda x: round(x.mean(), 4)),
                    vpd_max_fascia_kpa=("vpd_kpa", lambda x: round(x.max(), 4)),
                    vpd_min_fascia_kpa=("vpd_kpa", lambda x: round(x.min(), 4))
                )
                .sort_values(by=["data_previsione"])
            )
            st.caption(f"Riepilogo calcolato sulla fascia oraria **{h_min:02d}:00 – {h_max:02d}:00** ({h_max - h_min + 1} ore):")
            st.dataframe(df_agg, use_container_width=True)

    # TAB 4: ANAGRAFICA CENTRALINE & CONFIGURAZIONE GITHUB
    with tab_stations:
        st.subheader("🗺️ Elenco Ufficiale Centraline Pomodoro & File in `data/`")
        rows_anag = []
        for nome, cfg in STAZIONI.items():
            df_check = load_local_csv(cfg["csv_filename"])
            rows_anag.append({
                "Nome Stazione": nome,
                "Codice Stazione": cfg["codice"],
                "Latitudine WGS84 (°)": cfg["lat"],
                "Longitudine WGS84 (°)": cfg["lon"],
                "Percorso File GitHub / Locale": f"data/{cfg['csv_filename']}",
                "Totale Ore Consolidate": len(df_check),
                "Ultima Run Eseguita": df_check["data_run"].max() if not df_check.empty else "-"
            })
        st.dataframe(pd.DataFrame(rows_anag), use_container_width=True)

if __name__ == "__main__":
    main()
