"""
Modulo di esecuzione automatizzata (CLI / Headless) per lo scarico
delle previsioni orarie Open-Meteo per le 6 centraline del pomodoro (Run ore 07:00).

Protocollo operativo:
1. Interrogazione API Open-Meteo sui modelli ICON-EU ed ECMWF IFS025 per le 6 stazioni:
   - Braccagni (TOS11000008)
   - Capalbio (TOS11000006)
   - Cesa (TOS11000037)
   - Casotto dei Pescatori (TOS11000013)
   - Rispescia (TOS11000005)
   - San Donato (TOS03003099)
2. Media ensemble oraria di Temperatura (2m) e Umidità Relativa (2m).
3. Calcolo del VPD orario (kPa) secondo l'Equazione di Tetens.
4. Estrazione delle 72 ore (00:00 - 23:00) per:
   - D+0 (anticipo_giorni=0): ore 00:00-06:00 già trascorse + ore 07:00-23:00 del giorno corrente
   - D+1 (anticipo_giorni=1): 24 ore del giorno successivo
   - D+2 (anticipo_giorni=2): 24 ore di due giorni dopo
5. Sostituzione automatica nel CSV (data/<codice>_<nome>.csv) delle ore già presenti
   da run precedenti con i dati più freschi e precisi della run giornaliera (keep='last' su codice_stazione, data_previsione, ora).
"""

import sys
from datetime import datetime
from app_scarico_previsioni import (
    STAZIONI,
    process_station_forecast,
    load_local_csv,
    save_local_csv,
    merge_and_replace_fresher
)

def run_forecast_headless():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Avvio run giornaliera (D+0, D+1, D+2) previsioni orarie Open-Meteo (6 centraline pomodoro)...")

    success_count = 0
    total_stations = len(STAZIONI)

    for st_nome, cfg in STAZIONI.items():
        print(f"\n--- Elaborazione: {st_nome} (Codice: {cfg['codice']} | Coord: {cfg['lat']}, {cfg['lon']}) ---")
        try:
            _, df_hourly_new = process_station_forecast(st_nome, cfg)
            print(f"Dati orari D+0, D+1 e D+2 elaborati con successo ({len(df_hourly_new)} righe orarie estratte)")

            csv_name = cfg["csv_filename"]
            df_old = load_local_csv(csv_name)
            n_old = len(df_old)

            df_combined = merge_and_replace_fresher(df_old, df_hourly_new)
            n_replaced = (n_old + len(df_hourly_new)) - len(df_combined)

            saved_path = save_local_csv(df_combined, csv_name)
            print(
                f"Salvataggio completato: {saved_path} | "
                f"Ore preesistenti sostituite con dati più freschi: {n_replaced} | "
                f"Totale righe in archivio: {len(df_combined)}"
            )

            summary = (
                df_hourly_new.groupby(["data_run", "data_previsione", "anticipo_giorni"], as_index=False)
                .agg(
                    ore=("ora", "count"),
                    temp_media_24h=("temp_c", lambda x: round(x.mean(), 2)),
                    rh_media_24h=("rh_pct", lambda x: round(x.mean(), 2)),
                    vpd_medio_orario=("vpd_kpa", lambda x: round(x.mean(), 4)),
                    vpd_max_orario=("vpd_kpa", lambda x: round(x.max(), 4))
                )
            )
            print(summary.to_string(index=False))
            success_count += 1

        except Exception as e:
            print(f"ERRORE su {st_nome} ({cfg['codice']}): {e}", file=sys.stderr)

    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Run completata: {success_count}/{total_stations} centraline aggiornate nella cartella data/.")
    if success_count < total_stations:
        sys.exit(1)

if __name__ == "__main__":
    run_forecast_headless()
