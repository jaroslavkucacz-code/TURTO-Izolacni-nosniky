# Architektura TURTO 2.2+

## Cíl

Aplikace má jednu centrální AKCI a nad ní více produktových oblastí. Výpočtové moduly se mají měnit co nejméně; UI, aktualizace a kompatibilita se skládají kolem nich.

## Stabilní hranice

### Spouštění

`app.pyw` je malý bootstrap instalace. Po přípravě lokálního runtime spouští `app_runtime.pyw`.

Od 2.2.0 je `app_runtime.pyw` záměrně malý. Nastaví verzi aplikace, nainstaluje stabilní dekodér historických Schöck Dorn a předá řízení ověřenému aplikačnímu základu.

### Multi-domain platforma

`platform_workspace.py` je aktivní kompoziční vrstva UI.

Její úkol je:

- sestavit společnou AKCI,
- vložit aktivní produktové oblasti,
- skrýt neaktivní budoucí oblasti,
- připojit report celé AKCE,
- nepřenášet katalogové výpočty mezi doménami.

### Izolační nosníky

Výpočtové jádro HIT zůstává v ověřeném historickém řetězci. Aktuální soubor `hit_workspace.py` je veřejný vstup UI návrhu. Starší verzované moduly pod ním jsou **kompatibilní implementační vrstvy** a nemají být přímo importovány z nových částí platformy.

### Smykové trny

Od 2.2.0 platforma importuje pouze:

`shear_dowels_current.py`

Tento modul je stabilní veřejná hranice a aktuálně směruje na ověřenou implementaci 2.1.5.

Výpočtový katalog současných Ancon / Leviat a Schöck Stacon je oddělen od UI. Archivní Schöck Dorn je oddělen v `historical_schoeck_dorn.py`.

### Historický Schöck Dorn

Nové části aplikace používají `schoeck_dorn_decoder.py`.

Úplná historická označení SLD/SLD-Q a LD/LD-Q mohou používat archivní tabulkové VRd. Samostatná komponentová označení zůstávají pouze informativní.

## Data AKCE

Databáze AKCÍ je aplikační data, nikoli součást release balíčku. Aktualizátor ji nesmí přepisovat.

Změna schématu ukládaného payloadu musí být:

1. zpětně kompatibilní,
2. oddělená od aktualizace programových souborů,
3. ošetřená při načtení starší AKCE.

## Online aktualizace

`update_manifest.json` je jediný aktivní online release manifest.

Každá položka musí obsahovat:

- cílovou relativní cestu,
- RAW URL připnutou na 40znakový commit SHA,
- SHA-256 přesných bajtů stahovaného souboru.

Aktualizátor nesmí používat větev `main` jako zdroj programového souboru vydání.

## Historické vrstvy

Adresář `updates/` obsahuje starší verze, protože současný runtime na části ověřeného řetězce stále navazuje. **Nejde o kandidáty k hromadnému smazání.**

Technický úklid proto rozlišuje:

- **historickou kompatibilní vrstvu, která je stále importována** – zůstává,
- **starý build artefakt / jednorázový mezisoubor** – z aktuální větve se odstraní,
- **historický migrační nástroj, který má ještě smysl zachovat** – přesune se do `legacy/`.

## Pravidlo pro další vývoj

Nový kód nesmí přidávat další řetězec typu `module_216 -> module_215 -> module_214`, pokud to není nezbytné pro bezpečný hotfix.

Preferovaný postup:

1. opravit stabilní `*_current` hranici nebo vytvořit nový čistý modul,
2. starou implementaci ponechat pouze jako interní kompatibilitu,
3. přidat test/ověření, které brání návratu stejné regrese.
