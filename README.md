# TURTO – izolační nosníky a smykové trny

Vytvořil Ing. Jaroslav Kučera

**Aktuální vydání: TURTO 2.1.2**  
Produktové oblasti: **Izolační nosníky** + **Smykové trny**.

Lokální Windows aplikace pro práci s centrálními AKCEMI, dekódování výrobků, návrhy a katalogové záměny.

## Když se TURTO vůbec nespustí

Pokud je lokálně nainstalovaná verze, která spadne ještě před otevřením hlavního okna, nemůže se dostat k tlačítku **Aktualizace**. Pro tento stav je v kořeni repozitáře samostatná nouzová oprava:

1. Stáhněte aktuální ZIP repozitáře přes **Code → Download ZIP** a rozbalte jej.
2. Spusťte **`OPRAVIT_TURTO.bat`**.
3. Pokud se otevře výběr složky, vyberte svoji skutečnou instalační složku TURTO – tu, která obsahuje `app.pyw` nebo `Spustit_program.vbs`.
4. Oprava vytvoří zálohu stávající spouštěcí vrstvy, nainstaluje ověřený bootstrap TURTO 2.1.2 a vynutí nové rozbalení runtime při prvním startu.
5. **Databáze `actions.sqlite3` ani obsah uložených AKCÍ se nemění.**

Opravný nástroj ověřuje stažené soubory pomocí SHA-256. Průběh zapisuje do `recovery_2_1_2.log`. Pokud už bootstrap 2.1.2 naběhne, ale selže následný start runtime, úplný traceback se uloží do `startup_2_1_2.log` přímo v instalační složce TURTO.

## TURTO 2.1.2

- návrat na ověřený startovací řetězec 2.1.0 po regresi 2.1.1,
- izolační nosníky HIT zůstávají na stávajícím výpočtovém jádře včetně M–V interakce,
- smykové trny mají vlastní **Dekodér / Návrh / Záměny**,
- aktivní jsou současné návrhové a záměnové tabulky Ancon / Leviat a Schöck Stacon,
- historické Schöck Dorn značení je pouze pomůcka Dekodéru a nevstupuje do automatického návrhu ani záměn,
- centrální databáze AKCÍ se při runtime opravách nemění.

## Automatické aktualizace

Program používá `update_manifest.json` a při běžně funkčním startu stahuje pouze změněné programové soubory. Nouzová oprava výše je určena právě pro situaci, kdy se aplikace kvůli chybě před aktualizátorem vůbec neotevře.

---

## Původní přechod z v0.4.0 / v0.5.0 na GitHub základ

Historický GitHub základ byl verze 0.5.1. Jednorázový převod z velmi starých lokálních instalací zůstává v repozitáři jako **`00_INSTALOVAT_TURTO.bat`**.

Tento převod využívá existující funkční složku TURTO v0.4.0 nebo v0.5.0, zachová katalogová data a vytvoří zálohu měněných souborů. Pro současnou instalaci 2.x jej nepoužívejte jako opravný nástroj; při problému se startem použijte **`OPRAVIT_TURTO.bat`**.

## Důležité upozornění

Program je katalogová databázová a návrhová pomůcka. Nenahrazuje technické informace výrobce ani úplné statické posouzení. Před použitím ve výpočtu vždy ověřte celé označení, katalogové vydání, geometrické podmínky a zdrojové tabulky.
