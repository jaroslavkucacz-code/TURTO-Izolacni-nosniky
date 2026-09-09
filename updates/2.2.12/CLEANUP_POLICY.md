# TURTO 2.2.12 – pravidla úklidu instalace

Úklid je záměrně konzervativní.

## Vždy chráněné

- `app.pyw`
- `app_runtime.pyw`
- `app_runtime_202.pyw`
- `Spustit_program.vbs`
- `actions.sqlite3`
- `version.txt`
- `.turto_runtime_current.ok`
- všechny soubory uvedené v `REQUIRED_RUNTIME_FILES`

## Staré Python moduly

Kandidáti `app_central*.pyw`, `app_old*.pyw`, `app_legacy*.pyw`, `action_*.py` a `platform_*.py` se archivují pouze tehdy, pokud nejsou dosažitelné z aktuálního runtime přes importy / odkazy a nejsou používány spouštěcími skripty. Přesouvají se do `Archiv/Stare_moduly` místo mazání.

## Pomocné soubory

Jednorázové diagnostické a testovací skripty se přesouvají do `Nastroje/Diagnostika`. Historický soupis zdrojů Schöck se přesouvá do `Dokumentace/Zdroje`.

## Data

`actions.sqlite3` se nikdy nemaže, nepřesouvá ani nepřepisuje. Úklid nezasahuje do projektových dat ani katalogů.
