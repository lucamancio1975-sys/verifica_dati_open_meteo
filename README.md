# AgroMeteo Maremma - App Scarico Dati & Database Previsioni

Applicazione Streamlit per il download, l'elaborazione ed il salvataggio automatico delle previsioni meteorologiche future a 3 giorni da **Open-Meteo** (modelli **ICON-EU** ed **ECMWF IFS025**) per le stazioni di:
- **San Donato (Orbetello)**: Lat 42.554, Lon 11.237
- **Capalbio**: Lat 42.405, Lon 11.392
- **Rispescia (Alberese)**: Lat 42.706, Lon 11.145

---

## 💡 Caratteristiche Principali

1. **Scarto Automatico del Giorno 0 (Run Day)**:
   I dati orari del giorno della run vengono eliminati di default poiché i dati consuntivi vengono presi dal sito CFR Toscana.
2. **Estrazione Giorno 2 e Giorno 3**:
   Per ciascuna run vengono salvate le stime per i 2 giorni successivi alla data della run.
3. **Fascia Diurna 08:00 - 20:00**:
   Viene eseguita la media aritmetica pura per:
   - Temperatura Media Ensemble (°C)
   - Umidità Relativa Media Ensemble (%)
   - VPD Medio Stimato Ensemble (kPa) con la formula di Tetens.
4. **Tagging Arco Temporale (`anticipo_giorni`)**:
   Ogni riga salvata nel database reca il tag `anticipo_giorni` (`1` per la previsione del 2° giorno, `2` per la previsione del 3° giorno).
5. **Database CSV per Stazione**:
   Vengono aggiornati 3 file CSV distinti (`db_sandonato.csv`, `db_capalbio.csv`, `db_rispescia.csv`) nella cartella `./database/`.
6. **Sincronizzazione GitHub per Esecuzione da Smartphone**:
   Quando l'applicazione gira su **Streamlit Cloud**, ogni run aggiorna direttamente i file CSV sul repository GitHub via API REST, rendendo i dati archiviati permanenti anche quando la macchina virtuale viene riavviata.

---

## 🚀 Esecuzione su PC Locale

1. Installa le dipendenze:
   ```bash
   pip install -r requirements.txt
   ```
2. Avvia l'applicazione con il file batch `avvia_app.bat` oppure tramite comando:
   ```bash
   streamlit run app_scarico_previsioni.py
   ```

---

## 📱 Pubblicazione su Streamlit Cloud (per uso da Smartphone)

1. Pubblica questa cartella su un repository GitHub (es. `tuousername/agrometeo-maremma`).
2. Vai su [share.streamlit.io](https://share.streamlit.io) e collega il repository selezionando `app_scarico_previsioni.py` come file principale.
3. Vai nelle impostazioni dell'app su Streamlit Cloud (**App Settings -> Secrets**) e inserisci:
   ```toml
   GITHUB_TOKEN = "tuo_personal_access_token_github"
   GITHUB_REPO = "tuousername/agrometeo-maremma"
   GITHUB_BRANCH = "main"
   ```
4. Salva i Secrets. Ora potrai aprire il link fornito da Streamlit su qualsiasi smartphone e fare la run quotidiana con un semplice tocco!
