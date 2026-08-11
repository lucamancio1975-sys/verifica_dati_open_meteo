import os
import base64
import requests
import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta

# ==========================================
# CONFIGURAZIONE PAGINA E STILE STREAMLIT MOBILE-FIRST
# ==========================================
st.set_page_config(
    page_title="AgroMeteo Maremma - Database Previsioni",
    page_icon="⛅",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS per interfaccia moderna, pulita e responsiva (ottimizzata da Smartphone)
st.markdown("""
<style>
    /* Styling globale */
    .stApp {
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
        background-color: #f4f7f6;
    }
    
    /* Header Card */
    .header-card {
        background: linear-gradient(135deg, #1b4965 0%, #2b2d42 100%);
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
        color: #e0e6ed;
    }
    
    /* Metric & Info Cards */
    .info-card {
        background-color: #ffffff;
        border-left: 5px solid #2b2d42;
        padding: 14px 18px;
        border-radius: 10px;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
        margin-bottom: 16px;
        font-size: 0.95rem;
    }
    
    /* Pulsanti d'azione grandi e comodi da mobile */
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
    
    /* Responsive Dataframe */
    .stDataFrame {
        border-radius: 10px;
        overflow: hidden;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 1. CONFIGURAZIONE STAZIONI E COORDINATE
# ==========================================
STAZIONI = {
    "San Donato (Orbetello)": {
        "id_key": "sandonato",
        "lat": 42.554,
        "lon": 11.237,
        "csv_filename": "db_sandonato.csv"
    },
    "Capalbio": {
        "id_key": "capalbio",
        "lat": 42.405,
        "lon": 11.392,
        "csv_filename": "db_capalbio.csv"
    },
    "Rispescia (Alberese)": {
        "id_key": "rispescia",
        "lat": 42.706,
        "lon": 11.145,
        "csv_filename": "db_rispescia.csv"
    }
}

DB_DIR = "./database"

# ==========================================
# 2. FUNZIONI DI GESTIONE DATABASE E GITHUB
# ==========================================
def ensure_db_dir():
    """Crea la directory locale database se non esiste."""
    os.makedirs(DB_DIR, exist_ok=True)

def load_local_csv(csv_filename):
    """Carica il database CSV locale per la stazione specificata."""
    ensure_db_dir()
    filepath = os.path.join(DB_DIR, csv_filename)
    if os.path.exists(filepath):
        try:
            df = pd.read_csv(filepath)
            # Rinomina eventuali vecchie colonne 8_20 in 24h per retrocompatibilità
            rename_dict = {
                'temp_media_8_20': 'temp_media_24h',
                'rh_media_8_20': 'rh_media_24h',
                'vpd_medio_8_20': 'vpd_medio_24h'
            }
            return df.rename(columns=rename_dict)
        except Exception:
            pass
    return pd.DataFrame(columns=[
        'stazione', 'id_stazione', 'data_run', 'data_previsione',
        'anticipo_giorni', 'temp_media_24h', 'rh_media_24h', 'vpd_medio_24h'
    ])

def save_local_csv(df, csv_filename):
    """Salva il DataFrame nel file CSV locale."""
    ensure_db_dir()
    filepath = os.path.join(DB_DIR, csv_filename)
    df.to_csv(filepath, index=False, encoding='utf-8')
    return filepath

def get_github_secrets():
    """Restituisce i segreti GitHub se configurati nei secrets di Streamlit, altrimenti (None, None, None)."""
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
    Sincronizza il CSV sul repository GitHub se i Secret di Streamlit sono configurati.
    Richiede st.secrets["GITHUB_TOKEN"] e st.secrets["GITHUB_REPO"] (es. 'utente/repository').
    """
    token, repo, branch = get_github_secrets()
    if not token or not repo:
        return False, "Token GitHub o Nome Repository non configurati nei secret."

    repo_path = f"database/{csv_filename}"
    
    url = f"https://api.github.com/repos/{repo}/contents/{repo_path}"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    # 1. Recupera lo SHA se il file esiste già su GitHub
    sha = None
    try:
        get_res = requests.get(url, headers=headers, params={"ref": branch}, timeout=10)
        if get_res.status_code == 200:
            sha = get_res.json().get("sha")
    except Exception as e:
        return False, f"Impossibile verificare il file su GitHub: {e}"

    # 2. Prepara il contenuto CSV codificato in Base64
    csv_str = df.to_csv(index=False, encoding='utf-8')
    content_b64 = base64.b64encode(csv_str.encode('utf-8')).decode('utf-8')
    
    payload = {
        "message": f"🤖 Auto-update {csv_filename} da Streamlit Run",
        "content": content_b64,
        "branch": branch
    }
    if sha:
        payload["sha"] = sha
        
    try:
        put_res = requests.put(url, headers=headers, json=payload, timeout=12)
        if put_res.status_code in [200, 201]:
            return True, "CSV sincronizzato con successo su GitHub!"
        else:
            return False, f"GitHub API Errore ({put_res.status_code}): {put_res.text}"
    except Exception as e:
        return False, f"Errore durante l'invio su GitHub API: {e}"

# ==========================================
# 3. DOWNLOAD & ELABORAZIONE OPEN-METEO
# ==========================================
import time

def fetch_open_meteo_raw(lat, lon, retries=3):
    """
    Scarica i dati orari per 4 giorni dai modelli ICON-EU ed ECMWF IFS025 per Temp e RH.
    Include meccanismo di retry per gestire eventuali cali di connessione temporanei.
    """
    url = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={lat}&longitude={lon}&"
        f"hourly=temperature_2m,relative_humidity_2m&"
        f"models=icon_eu,ecmwf_ifs025&"
        f"timezone=Europe%2FRome&forecast_days=4"
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
    Scarica ed elabora la previsione per una stazione:
    1. Ensemble orario Temp, RH, VPD (Formula Tetens)
    2. Scarto dati orari del giorno della run (Day 0)
    3. Estrazione Giorno +1 (anticipo_giorni=1) e Giorno +2 (anticipo_giorni=2)
    4. Calcolo medie sull'intero arco delle 24 ore (00:00 - 23:00)
    """
    raw_data = fetch_open_meteo_raw(config["lat"], config["lon"])
    hourly = raw_data.get("hourly", {})
    
    times = hourly.get("time", [])
    t_icon = hourly.get("temperature_2m_icon_eu", [])
    rh_icon = hourly.get("relative_humidity_2m_icon_eu", [])
    t_ecmwf = hourly.get("temperature_2m_ecmwf_ifs025", [])
    rh_ecmwf = hourly.get("relative_humidity_2m_ecmwf_ifs025", [])
    
    if not (times and t_icon and rh_icon and t_ecmwf and rh_ecmwf):
        raise ValueError(f"Dati API incompleti per {stazione_nome}")

    df_hourly = pd.DataFrame({
        'time_raw': times,
        'temp_icon_eu': t_icon,
        'rh_icon_eu': rh_icon,
        'temp_ecmwf': t_ecmwf,
        'rh_ecmwf': rh_ecmwf
    })

    dt_series = pd.to_datetime(df_hourly['time_raw'])
    df_hourly['date'] = dt_series.dt.date
    df_hourly['hour'] = dt_series.dt.hour
    
    # Ensemble Temp & RH
    df_hourly['temp_ensemble'] = (df_hourly['temp_icon_eu'] + df_hourly['temp_ecmwf']) / 2.0
    df_hourly['rh_ensemble'] = (df_hourly['rh_icon_eu'] + df_hourly['rh_ecmwf']) / 2.0

    # Formula di Tetens per VPD orario (kPa)
    t_ens = df_hourly['temp_ensemble']
    rh_ens = df_hourly['rh_ensemble']
    e_s = 0.61078 * np.exp((17.27 * t_ens) / (t_ens + 237.3))
    e_a = e_s * (rh_ens / 100.0)
    df_hourly['vpd_ensemble_kpa'] = e_s - e_a

    # Determinazione data della Run (Oggi o data custom)
    if date_run_custom:
        run_date = date_run_custom
    else:
        run_date = dt_series.dt.date.min() # Data di inizio delle previsioni (giorno run)

    giorno_1 = run_date + timedelta(days=1)
    giorno_2 = run_date + timedelta(days=2)

    giorni_target = [
        (giorno_1, 1),
        (giorno_2, 2)
    ]

    nuove_righe = []

    for g_target, anticipo in giorni_target:
        # Filtro: Data target su l'intero arco delle 24 ore (00:00 - 23:00)
        mask = (df_hourly['date'] == g_target)
        df_sub = df_hourly[mask]
        
        if not df_sub.empty:
            t_mean = round(df_sub['temp_ensemble'].mean(), 2)
            rh_mean = round(df_sub['rh_ensemble'].mean(), 2)
            vpd_mean = round(df_sub['vpd_ensemble_kpa'].mean(), 4)
            
            nuove_righe.append({
                'stazione': stazione_nome,
                'id_stazione': config['id_key'],
                'data_run': run_date.strftime('%Y-%m-%d'),
                'data_previsione': g_target.strftime('%Y-%m-%d'),
                'anticipo_giorni': anticipo,
                'temp_media_24h': t_mean,
                'rh_media_24h': rh_mean,
                'vpd_medio_24h': vpd_mean
            })

    df_daily_summary = pd.DataFrame(nuove_righe)
    return df_hourly, df_daily_summary

def update_station_database(stazione_nome, config, df_new_daily):
    """
    Unisce le nuove righe estratte dalla run al database CSV della stazione.
    Rimuove eventuali duplicati per la combinazione (id_stazione, data_run, data_previsione).
    """
    csv_name = config["csv_filename"]
    df_old = load_local_csv(csv_name)
    
    if df_old.empty:
        df_combined = df_new_daily
    else:
        df_combined = pd.concat([df_old, df_new_daily], ignore_index=True)

    # Rimozione duplicati
    df_combined = df_combined.drop_duplicates(
        subset=['id_stazione', 'data_run', 'data_previsione'],
        keep='last'
    )
    
    # Ordinamento per data_previsione e poi data_run
    df_combined['data_previsione'] = df_combined['data_previsione'].astype(str)
    df_combined['data_run'] = df_combined['data_run'].astype(str)
    df_combined = df_combined.sort_values(by=['data_previsione', 'data_run'], ascending=[True, True])
    
    # Salvataggio Locale
    local_path = save_local_csv(df_combined, csv_name)
    
    # Sincronizzazione GitHub (se attiva nei Secret)
    gh_success, gh_msg = sync_github_csv(csv_name, df_combined)
    
    return df_combined, local_path, gh_success, gh_msg

# ==========================================
# 4. INTERFACCIA UTENTE STREAMLIT (UI)
# ==========================================
def main():
    # Intestazione Principale
    st.markdown("""
    <div class="header-card">
        <h1>⛅ AgroMeteo Maremma</h1>
        <p>Database Previsioni 3 Stazioni (San Donato, Capalbio, Rispescia)<br>Medie Giornaliere 24h & Calcolo VPD</p>
    </div>
    """, unsafe_allow_html=True)

    # Controllo stato GitHub Sync nei Secret
    gh_token, gh_repo, _ = get_github_secrets()
    gh_configured = bool(gh_token and gh_repo)
    
    # Barra laterale (o menu espandibile per mobile)
    st.sidebar.header("⚙️ Pannello di Controllo")
    st.sidebar.info(
        f"**Stazioni Agrometeo**:\n"
        f"• San Donato: (42.554°N, 11.237°E)\n"
        f"• Capalbio: (42.405°N, 11.392°E)\n"
        f"• Rispescia: (42.706°N, 11.145°E)\n\n"
        f"**Fascia Oraria**: 24h (Intero arco giornaliero)\n"
        f"**Sincronizzazione GitHub**: {'✅ Attiva' if gh_configured else '⚠️ Solo Locale (Configura Secrets)'}"
    )

    # Pulsante d'azione principale
    st.markdown("""
    <div class="info-card">
        📲 <strong>Esecuzione Run Daily:</strong> Scarica le previsioni Open-Meteo (ICON-EU + ECMWF), elimina i dati del giorno corrente, estrae i 2 giorni successivi sull'intero arco delle 24 ore con il tag di anticipo (1d o 2d) e aggiorna i database CSV per ogni stazione.
    </div>
    """, unsafe_allow_html=True)

    btn_run = st.button("🚀 ESEGUI RUN PREVISIONI (TUTTE LE 3 STAZIONI)", use_container_width=True)

    if btn_run:
        with st.spinner("⏳ Connessione ad Open-Meteo, calcolo medie 24h e aggiornamento database CSV..."):
            esiti = {}
            for st_nome, cfg in STAZIONI.items():
                try:
                    df_h, df_daily = process_station_forecast(st_nome, cfg)
                    df_updated, local_p, gh_ok, gh_msg = update_station_database(st_nome, cfg, df_daily)
                    esiti[st_nome] = {
                        "df_daily": df_daily,
                        "df_db": df_updated,
                        "local_path": local_p,
                        "gh_ok": gh_ok,
                        "gh_msg": gh_msg
                    }
                except Exception as e:
                    st.error(f"❌ Errore durante l'elaborazione per **{st_nome}**: {e}")

        if esiti:
            st.success("✅ Run completata con successo per tutte le 3 stazioni!")
            for st_nome, res in esiti.items():
                with st.expander(f"📍 Risultati Run: **{st_nome}**", expanded=True):
                    st.markdown("**Nuovi Dati Calcolati per la Run di Oggi (Medie 24 Ore):**")
                    st.dataframe(res["df_daily"], use_container_width=True)
                    if res["gh_ok"]:
                        st.caption(f"🟢 GitHub Sync: {res['gh_msg']}")
                    else:
                        st.caption(f"💾 Salvato in locale: `{res['local_path']}` ({res['gh_msg']})")

    st.markdown("---")

    # SEZIONE TAB DI CONSULTAZIONE
    tab_db, tab_charts, tab_info = st.tabs([
        "🗃️ Database CSV Stazioni",
        "📈 Grafici & Confronto Anticipi",
        "⚙️ Configurazione & Guida GitHub"
    ])

    # TAB 1: DATABASE CSV STAZIONI
    with tab_db:
        st.subheader("📊 Archivio Database Cumulativo delle Previsioni")
        st.write("Seleziona una stazione per visualizzare il registro completo o scaricare il file CSV:")
        
        st_scelta = st.selectbox("Seleziona Stazione", list(STAZIONI.keys()))
        cfg_scelta = STAZIONI[st_scelta]
        
        df_db_curr = load_local_csv(cfg_scelta["csv_filename"])
        
        if df_db_curr.empty:
            st.info(f"Nessun dato ancora archiviato per **{st_scelta}**. Fai clic su '🚀 ESEGUI RUN PREVISIONI' in alto.")
        else:
            st.dataframe(df_db_curr, use_container_width=True)
            
            # Pulsante per download diretto da smartphone
            csv_bytes = df_db_curr.to_csv(index=False, encoding='utf-8').encode('utf-8')
            st.download_button(
                label=f"📥 Scarica {cfg_scelta['csv_filename']}",
                data=csv_bytes,
                file_name=cfg_scelta['csv_filename'],
                mime="text/csv",
                use_container_width=True
            )

    # TAB 2: GRAFICI INTERATTIVI
    with tab_charts:
        st.subheader("📈 Analisi Previsioni & Confronto Giorni di Anticipo")
        st_graf = st.selectbox("Seleziona Stazione per i Grafici", list(STAZIONI.keys()), key="graf_sel")
        cfg_graf = STAZIONI[st_graf]
        df_db_graf = load_local_csv(cfg_graf["csv_filename"])
        
        if df_db_graf.empty:
            st.info("Nessun dato disponibile nel database per generare i grafici.")
        else:
            # Grafico VPD Medio Stimato 24h per Data Previsione
            fig_vpd = px.line(
                df_db_graf,
                x="data_previsione",
                y="vpd_medio_24h",
                color="anticipo_giorni",
                markers=True,
                labels={"anticipo_giorni": "Anticipo (Giorni)", "vpd_medio_24h": "VPD Medio 24h (kPa)", "data_previsione": "Data Prevista"},
                title=f"VPD Medio 24h - {st_graf} (1d vs 2d anticipo)"
            )
            fig_vpd.update_layout(template="plotly_white", hovermode="x unified")
            st.plotly_chart(fig_vpd, use_container_width=True)
            
            col_t, col_rh = st.columns(2)
            with col_t:
                fig_t = px.bar(
                    df_db_graf,
                    x="data_previsione",
                    y="temp_media_24h",
                    color="anticipo_giorni",
                    barmode="group",
                    labels={"temp_media_24h": "Temp Media 24h (°C)"},
                    title=f"Temperatura Media 24h (°C)"
                )
                fig_t.update_layout(template="plotly_white")
                st.plotly_chart(fig_t, use_container_width=True)
                
            with col_rh:
                fig_rh = px.bar(
                    df_db_graf,
                    x="data_previsione",
                    y="rh_media_24h",
                    color="anticipo_giorni",
                    barmode="group",
                    labels={"rh_media_24h": "RH Media 24h (%)"},
                    title=f"Umidità Relativa Media 24h (%)"
                )
                fig_rh.update_layout(template="plotly_white")
                st.plotly_chart(fig_rh, use_container_width=True)

    # TAB 3: GUIDA & CONFIGURAZIONE STREAMLIT CLOUD
    with tab_info:
        st.subheader("⚙️ Configurazione GitHub Sync per Streamlit Cloud")
        st.markdown("""
        Per consentire all'applicazione pubblicata su **Streamlit Community Cloud** di aggiornare automaticamente i file CSV nel tuo repository GitHub ad ogni run eseguita da Smartphone, segui questi passaggi:
        
        1. Crea un **Personal Access Token (PAT)** su GitHub con permessi di scrittura (`repo` / `contents: write`).
        2. Nella dashboard di **Streamlit Cloud**, vai nelle impostazioni della tua app -> **Secrets**.
        3. Aggiungi le seguenti chiavi:
        
        ```toml
        GITHUB_TOKEN = "ghp_il_tuo_token_segreto_qui"
        GITHUB_REPO = "tuo_utente_github/nome_repository"
        GITHUB_BRANCH = "main"
        ```
        
        In questo modo, ad ogni pressione del tasto **🚀 ESEGUI RUN PREVISIONI** da Smartphone, l'app scaricherà i nuovi dati Open-Meteo, calcolerà le medie 24h e committerà il CSV aggiornato direttamente nel tuo repository GitHub!
        """)

if __name__ == "__main__":
    main()
