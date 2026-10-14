"""
Modulo di esecuzione automatizzata (CLI / Headless) per lo scarico
delle previsioni Open-Meteo per le stazioni di Maremma.

Esegue:
1. Download previsioni ensemble (ICON-EU + ECMWF) per San Donato, Capalbio e Rispescia.
2. Scarto dei dati Day 0 (giorno run).
3. Calcolo medie 24h per Day+1 e Day+2 (Temp, RH, VPD Formula di Tetens).
4. Aggiornamento CSV locali nella cartella database/ (con deduplicazione).
"""

import sys
import os
from datetime import datetime

# Importa le costanti e le funzioni di calcolo dal file applicativo principale
from app_scarico_previsioni import (
    STAZIONI,
    process_station_forecast,
    load_local_csv,
    save_local_csv
)

def run_forecast_headless():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Avvio run automatica previsioni Open-Meteo...")
    
    success_count = 0
    total_stations = len(STAZIONI)
    
    for st_nome, cfg in STAZIONI.items():
        print(f"\n--- Elaborazione: {st_nome} (ID: {cfg['id_key']}) ---")
        try:
            _, df_daily = process_station_forecast(st_nome, cfg)
            print(f"Previsioni elaborate con successo ({len(df_daily)} righe)")
            
            # Carica vecchio CSV e unisci
            csv_name = cfg["csv_filename"]
            df_old = load_local_csv(csv_name)
            
            import pandas as pd
            if df_old.empty:
                df_combined = df_daily
            else:
                df_combined = pd.concat([df_old, df_daily], ignore_index=True)
                
            # Deduplicazione su (id_stazione, data_run, data_previsione)
            df_combined = df_combined.drop_duplicates(
                subset=['id_stazione', 'data_run', 'data_previsione'],
                keep='last'
            )
            df_combined['data_previsione'] = df_combined['data_previsione'].astype(str)
            df_combined['data_run'] = df_combined['data_run'].astype(str)
            df_combined = df_combined.sort_values(by=['data_previsione', 'data_run'], ascending=[True, True])
            
            saved_path = save_local_csv(df_combined, csv_name)
            print(f"Salvataggio database completato: {saved_path} (Totale righe: {len(df_combined)})")
            
            # Stampa anteprima ultime righe
            print(df_daily[['data_run', 'data_previsione', 'anticipo_giorni', 'temp_media_24h', 'rh_media_24h', 'vpd_medio_24h']].to_string(index=False))
            success_count += 1
            
        except Exception as e:
            print(f"ERRORE su {st_nome}: {e}", file=sys.stderr)
            
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Run completata: {success_count}/{total_stations} stazioni aggiornate.")
    if success_count < total_stations:
        sys.exit(1)

if __name__ == "__main__":
    run_forecast_headless()
