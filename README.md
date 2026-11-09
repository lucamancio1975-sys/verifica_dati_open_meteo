# 🍅 AgroMeteo Centraline Pomodoro – Previsioni Orarie VPD (Open-Meteo)

Applicazione **Streamlit** e script di automazione headless per lo scarico giornaliero (cron-job ore **07:00**) dei dati orari Open-Meteo e il calcolo del **VPD orario (Equazione di Tetens)** sulle **6 centraline di riferimento per il pomodoro**.

---

## 📍 Centraline Monitorate (Coordinate WGS84)

| Nome Stazione | Codice Stazione | Latitudine (°N) | Longitudine (°E) | File Archivio (`data/`) |
| :--- | :---: | :---: | :---: | :--- |
| **Braccagni** | `TOS11000008` | `42.931` | `11.080` | `data/TOS11000008_braccagni.csv` |
| **Capalbio** | `TOS11000006` | `42.405` | `11.392` | `data/TOS11000006_capalbio.csv` |
| **Cesa** | `TOS11000037` | `43.308` | `11.825` | `data/TOS11000037_cesa.csv` |
| **Casotto dei Pescatori** | `TOS11000013` | `42.769` | `11.016` | `data/TOS11000013_casotto_dei_pescatori.csv` |
| **Rispescia** | `TOS11000005` | `42.706` | `11.145` | `data/TOS11000005_rispescia.csv` |
| **San Donato** | `TOS03003099` | `42.554` | `11.237` | `data/TOS03003099_san_donato.csv` |

---

## ⚙️ Protocollo di Scarico e Sostituzione Dati Freschi (Run ore 07:00)

1. **Interrogazione Multi-Modello Open-Meteo:**
   - Modelli previsionali: **`icon_eu`** + **`ecmwf_ifs025`**
   - Variabili orarie: `temperature_2m` (°C) e `relative_humidity_2m` (%)
   - Fuso orario: `Europe/Rome`
2. **Media Ensemble Oraria:**
   - $T_{\text{ens}}(h) = \frac{T_{\text{ICON-EU}}(h) + T_{\text{ECMWF}}(h)}{2}$
   - $RH_{\text{ens}}(h) = \frac{RH_{\text{ICON-EU}}(h) + RH_{\text{ECMWF}}(h)}{2}$
3. **Calcolo VPD Orario (Equazione di Tetens in kPa):**
   $$e_s(T) = 0.61078 \cdot \exp\left(\frac{17.27 \cdot T_{\text{ens}}}{T_{\text{ens}} + 237.3}\right)$$
   $$e_a(T, RH) = e_s(T) \cdot \frac{RH_{\text{ens}}}{100}$$
   $$\text{VPD}(h) = e_s(T) - e_a(T, RH)$$
4. **Orizzonte Giornaliero (`D+0`, `D+1` e `D+2` – 72 ore per run):**
   - **`D+0` (`anticipo_giorni = 0`):** scarica le ore già trascorse del giorno corrente (`00:00 - 06:00`) + la previsione fino a fine giornata (`07:00 - 23:00`).
   - **`D+1` (`anticipo_giorni = 1`):** scarica le 24 ore (`00:00 - 23:00`) del giorno successivo.
   - **`D+2` (`anticipo_giorni = 2`):** scarica le 24 ore (`00:00 - 23:00`) di due giorni dopo.
5. **Sostituzione Automatica con i Dati più Freschi (`merge_and_replace_fresher`):**
   - Ad ogni run, le ore già presenti in archivio da run precedenti (es. le ore che ieri erano `D+1` o `D+2`) vengono **automaticamente sostituite** (`drop_duplicates(subset=["codice_stazione", "data_previsione", "ora"], keep="last")`) con i valori più freschi e precisi dell'ultima run.

---

## ⏰ Configurazione Cron-Job.org (Ore 07:00)

Per attivare automaticamente il workflow ogni mattina alle **07:00** da **cron-job.org**:
- **URL:** `https://api.github.com/repos/lucamancio1975-sys/verifica_dati_open_meteo/actions/workflows/run_forecast.yml/dispatches`
- **Request Method:** `POST`
- **Timezone:** `Europe/Rome` (Orario: `07:00`)
- **Headers:**
  - `Accept`: `application/vnd.github+json`
  - `Authorization`: `Bearer <IL_TUO_GITHUB_TOKEN>`
  - `Content-Type`: `application/json`
  - `User-Agent`: `cron-job-org`
- **Request Body:**
  ```json
  {"ref":"main"}
  ```
