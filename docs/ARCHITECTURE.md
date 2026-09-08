# Architektura TURTO 2.2+

## Cíl

Aplikace má jednu centrální AKCI a nad ní více produktových oblastí. Výpočtové moduly se mají měnit co nejméně; UI, aktualizace a kompatibilita se skládají kolem nich.

## Stabilní hranice

### Spouštění

`app.pyw` je malý bootstrap instalace. Po přípravě lokálního runtime spouští `app_runtime.pyw`.

Od 2.2.1 bootstrap používá obecný marker `.turto_runtime_current.ok` a diagnostiku `startup.log`. Bootstrap obsahuje připnutý commit a SHA-256 svého `runtime_installer.py`; pokud lokální runtime není kompletní nebo marker neodpovídá aktuálnímu layoutu, spustí kontrolovanou obnovu.

`runtime_layout` je oddělený od čísla vydání. Běžná verze aplikace se proto může změnit bez zbytečné reinstalace celé kompatibilní runtime sady. Layout se zvýší pouze tehdy, když se skutečně změní požadovaná struktura runtime.

`app_runtime.pyw` je záměrně malý. Nastaví verzi aplikace, nainstaluje stabilní dekodér historických Schöck Dorn a předá řízení ověřenému aplikačnímu základu.

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

Tento řetězec se nemá hromadně zplošťovat pouze kvůli názvům souborů. Je stále živou kompatibilní součástí programu a případné sloučení vyžaduje samostatnou regresní kontrolu výpočtů, importů a UI.

### Smykové trny

Od 2.2.0 platforma importuje pouze:

`shear_dowels_current.py`

Tento modul je stabilní veřejná hranice a aktuálně směruje na ověřenou implementaci 2.1.5.

Výpočtový katalog současných Ancon / Leviat a Schöck Stacon je oddělen od UI. Archivní Schöck Dorn je oddělen v `historical_schoeck_dorn.py`.

### Historický Schöck Dorn

Nové části aplikace používají `schoeck_dorn_decoder.py`.

Úplná historická označení SLD/SLD-Q a LD/LD-Q mohou používat archivní tabulkové VRd. Samostatná komponentová označení zůstávají pouze informativní.

## Data AKCE

Databáze `actions.sqlite3` je aplikační data, nikoli součást release balíčku. Aktualizátor ani recovery ji nesmí přepisovat.

Od 2.2.1 je ochrana dvojí:

- release manifest nesmí mít `actions.sqlite3` jako cílovou cestu,
- updater má `actions.sqlite3` ve výslovném seznamu chráněných cílů a takový manifest odmítne i za běhu.

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

Manifest navíc obsahuje `runtime_layout`, který musí souhlasit s bootstrapem.

Aktualizátor od 2.2.1 pracuje transakčně:

1. validuje celý manifest,
2. stáhne a ověří všechny soubory,
3. před zápisem zazálohuje všechny existující cíle,
4. soubory nahrazuje přes dočasné soubory a `os.replace`,
5. při chybě obnoví původní soubory a odstraní nově vytvořené cíle,
6. teprve po úspěchu zapíše verzi a runtime marker.

Průběh aplikační části aktualizace se ukládá do `update_apply.log`.

## Nouzová oprava

`OPRAVIT_TURTO.bat` a `OPRAVIT_TURTO.ps1` jsou pouze recovery cesta pro stav, kdy se UI vůbec nedostane k běžné aktualizaci.

Recovery:

- zálohuje pouze spouštěcí vrstvu a diagnostické markery,
- stahuje stejné commit-pinned `app.pyw` a `updater.py` jako aktuální manifest,
- ověřuje SHA-256,
- odstraní aktuální runtime marker a tím vynutí ověřenou obnovu při následujícím startu,
- nemění `actions.sqlite3`.

Aktuální recovery log je `recovery.log`; startup traceback je `startup.log`. Staré názvy 2.1.2 se v recovery používají pouze pro jednorázovou zálohu/úklid z dřívějších instalací.

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
