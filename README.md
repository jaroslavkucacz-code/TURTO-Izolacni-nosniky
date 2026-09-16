# TURTO Statika 3.0.12

[Stáhnout TURTO Statika pro Windows (ZIP)](https://github.com/jaroslavkucacz-code/TURTO-Izolacni-nosniky/releases/download/v3.0.12/TURTO-Statika-3.0.12-Windows-x64.zip)

Rozbalte celý balíček a spusťte **TURTO Statika.exe**. Python se neinstaluje. Při přechodu ze stávajícího programu zkopírujte obsah balíčku do jeho dosavadní složky; databáze AKCÍ a nastavení nejsou součástí balíčku. Podrobnosti: [návod k EXE](packaging/windows/CTETE_ME.txt).

Plynulejší posouvání tabulky HIT a přepínání modulů. Odstraněné opakované průchody celým rozhraním, zachování panelu při přepnutí a stabilní zobrazení řádků.

Jednotky návrhu HIT na metr nebo na prvek, samostatně pro každý řádek. Přepočet podle délky každé varianty, uložení do AKCE a správné jednotky v PDF, Excelu i schránce. V Desky / balkony vyberte u řádku **Jednotky účinků**. Přepnutí ponechá zadaná čísla a přepočítá návrh; 20 kN/prvek při délce 500 mm odpovídá 40 kN/m. Počet kusů přepočet neovlivňuje. Starší AKCE se načítají v původních jednotkách na metr.

Ručně vybraný HIT zůstává zachovaný při přepnutí mezi Desky / balkony, Doplňkové prvky a Stěny WT, přidání řádku v jiném modulu i opuštění políčka. Opraven také souběh ruční volby s odloženým přepočtem. Skutečné změny návrhových parametrů nadále spouštějí nový návrh.

Opravena záměna dekódovaného Schöck T-QP-VV za HIT-HP ZDX. U dříve uložené AKCE stačí na kartě záměn znovu použít **Navrhnout vše**. Zdrojové CV se nedoplňuje; cílové krytí ZDX je pevně 30 mm. Kontroly únosnosti, geometrie, délky, izolantu, betonu a ložisek zůstávají aktivní.

Doplněna skutečná tabulka Schöck T-QP-VV generace 5.0 ze zdroje AT/2025.1. Označení `T-QP-VV1-REI120-H200-L300-5.0` funguje v běžném dekodéru i hromadném importu; zachová H200, L300, 80 mm izolantu a ±30,9 kN/prvek pro C25/30. Zdroj a jeho otisk jsou v `updates/3.0.7/schoeck_t_qp_307.json`.

Moduly Desky / balkony, Doplňkové prvky a Stěny WT začínají prázdné. Nová AKCE ani načtení prázdného návrhu automaticky nepřidává první řádek. Přehled AKCÍ nezapočítává přesně rozpoznané starší výchozí řádky bez úprav; změněné a výslovně přidané návrhy se zachovávají i nedokončené. Přepočet počtů při zobrazení seznamu je pouze čtecí, bez migrace databáze. Podrobnosti v `updates/3.0.6/RELEASE_NOTES.txt`.

PDF výstupy všech částí nosníků a trnů používají standardní firemní logo TURTO z dodaného PNG. Logo je na každé stránce v původní kvalitě, s průhledností a zachovanými proporcemi. Symbol a ikona uvnitř programu zůstávají beze změny. Podrobnosti v `updates/3.0.5/RELEASE_NOTES.txt`.

Přesné rozpoznání explicitních T/XT/CXT označení a oprava exportu PDF přímo z dat AKCE. PDF zachovává celé záměny, rozměry, směrové kontroly, jednotky na prvek a skutečné využití; chybějící data nemohou vytvořit falešné VYHOVUJE / 0,0 %. CXT AP zůstává zvláštním posouzením KF. Podrobnosti v `updates/3.0.4/RELEASE_NOTES.txt`.


Vytvořil Ing. Jaroslav Kučera

**Aktuální vydání: TURTO 3.0.11** (`3.0.11`)

TURTO je lokální Windows aplikace pro jednu společnou **AKCI** a více produktových oblastí. Aktuálně jsou aktivní:

- **Izolační nosníky** – Dekodér / Návrh / Záměny
- **Smykové trny** – Dekodér / Návrh / Záměny

Zachována oprava z TURTO 3.0.1: načítání schváleného symbolu v záhlaví a ikoně hlavního okna a skutečná průběžná klasifikace hromadného výkazu. Úplné označení XT se nehledá mezi nesouvisejícími obecnými návrhy; chybějící katalogový záznam je označen **Chybí data**. Tato oprava dekodéru sama nedoplňuje chybějící tabulky Schöck; doplnění HIT Annexu 3 ve verzi 3.0.3 je samostatně kontrolované podle zdrojového DoP. Testovací data TEST_ONLY se do aplikace nedodávají.

## Aktuální funkce

### Izolační nosníky
- EBEA/TEBEA ve společném Dekodéru, Návrhu a Záměnách; Peikko se volí jako výrobce,
- úplné rozlišení konfigurace (Ds, Dt, SW, L, S11, RS/VE1, B2, REI, OQ) a hromadné vložení,
- Peikko: ověřené tabulky EBEA-100/E-100/700, součásti TEBEA ETA a omezené porovnání M/V; bez automaticky potvrzené statické záměny,
- jeden společný formulář návrhu Leviat / Peikko; stejné vstupy a zachování hodnot při přepnutí výrobce,
- společné zadání uložené v AKCI; katalogová specifika, rozteč a původní výkaz HIT v Pokročilých,
- doložené standardní D, jednotky na prvek / na metr se zatěžovací šířkou, lokální zdrojové PDF s SHA kontrolou,
- dekódování katalogových označení,
- hromadné vložení z výkazu,
- návrh Leviat HIT,
- katalogové záměny s kontrolou geometrie, krytí, výšky, betonu, tlakového přenosu a únosností,
- bezpečné rozlišení geometrických variant OU / OD.

### Smykové trny
- Ancon / Leviat,
- Schöck Stacon + podporované historické Schöck Dorn,
- PohlCon HED / JDSD / JDSDQ,
- MAX FRANK Egcodorn / Egcodubel,
- jednosměrné a obousměrné varianty,
- Dekodér / Návrh / Záměny se společným ovládáním a hromadným vložením z výkazu.

### Společná AKCE
Dekódované prvky, návrhy a záměny obou produktových oblastí se ukládají společně v centrální AKCI. Databáze `actions.sqlite3` je při online aktualizacích chráněná a není součástí release manifestu.

## PDF

Od TURTO 2.2.8 používá hlavní tlačítko **Export PDF…** výběr rozsahu. Lze exportovat:

- celou AKCI,
- všechny Izolační nosníky,
- Izolační nosníky → Dekodér / Návrh / Záměny,
- všechny Smykové trny,
- Smykové trny → Dekodér / Návrh / Záměny.

Obecné vysvětlivky jsou soustředěné v **Nápovědě**, aby nezabíraly pracovní plochu. Technické údaje, katalogové zdroje, stavy a varování zůstávají v detailech a výsledcích.

## Online aktualizace

V běžně funkční aplikaci použijte **Aktualizace**. Aktualizátor:

1. načte `update_manifest.json` přednostně přes GitHub API,
2. odmítne chráněné cíle včetně `actions.sqlite3`,
3. stáhne soubory z adres připnutých na konkrétní commit a ověří SHA-256,
4. vytvoří zálohu měněných souborů v `.update_backup`,
5. nahradí soubory transakčně,
6. při chybě provede rollback,
7. po úspěchu zapíše verzi/runtime marker a program znovu spustí.

Průběh aktualizace se zapisuje do `update_apply.log`.

## Když se TURTO nespustí

V kořeni repozitáře je nouzová cesta:

- `OPRAVIT_TURTO.bat`
- `OPRAVIT_TURTO.ps1`

Nouzová oprava obnovuje ověřený bootstrap a updater, ale nemění databázi AKCÍ. Diagnostika je v `recovery.log`; chyba následného startu v `startup.log`.

## Vývoj a kontrola vydání

Aktivní kontrolní workflow:

```text
.github/workflows/ci.yml
```

Kontroluje mimo jiné:

- release manifest, SHA-256 a připnuté commit URL,
- bootstrap / runtime installer / recovery,
- ochranu `actions.sqlite3`,
- směr pohybu smykových trnů a historické Q varianty,
- záměny Schöck Isokorb a geometrii OU/OD,
- PohlCon a MAX FRANK,
- jednotné tabulky a ovládání,
- rozsah PDF exportu,
- Windows PowerShell recovery,
- skutečné aktualizace 3.0.1 → 3.0.2, 3.0.2 → 3.0.3 a 3.0.3 → 3.0.4 a tlačítko Navrhnout vše na Windows/Linux,
- původní Annex 3 přímo z ověřeného DoP, opravu staršího souboru HIT v paměti, přepočet kN/m na skutečný prvek, pozice P021/P025/P026/P027, ochranu nesrovnalých dat a SQLite round-trip.

Hlavní dokumentace:

- `docs/ARCHITECTURE.md`
- `docs/RELEASE_PROCESS.md`
- `updates/<verze>/RELEASE_NOTES.txt`

Historické migrační nástroje jsou oddělené v `legacy/` a pro současné instalace se nepoužívají.

## Důležité upozornění

TURTO je katalogová databázová a návrhová pomůcka. Nenahrazuje technické informace výrobce ani úplné statické posouzení. Před použitím ve výpočtu vždy ověřte celé označení, katalogové vydání, geometrické podmínky a zdrojové tabulky.

## Ověření 3.0.4

`tools/verify_decoder_pdf_304.py` ověřuje skutečný přechod 3.0.3 → 3.0.4, tlačítka Analyzovat a Navrhnout vše, všech šest rozsahů PDF, uložení do SQLite, vybranou variantu, momentové a smykové jednotky a odmítnutí neúplných výsledků. Překlady a pořadí sloupců GUI nemají ovlivnit PDF. Schématové katalogy TEST_ONLY se do instalace nedodávají. Původní chybné exporty znovu vytvořte z AKCE; samotné neúplné PDF neobsahuje všechna potřebná data.

