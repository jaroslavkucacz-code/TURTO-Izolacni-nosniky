# TURTO – izolační nosníky a smykové trny

Vytvořil Ing. Jaroslav Kučera

**Aktuální vydání: TURTO 2.1.4**  
Produktové oblasti: **Izolační nosníky** + **Smykové trny**.

Lokální Windows aplikace pro práci s centrálními AKCEMI, dekódování výrobků, návrhy a katalogové záměny.

## TURTO 2.1.4

Smykové trny používají stejný základní pracovní model jako izolační nosníky:

- **Dekodér**: jednotlivé zadání i **Hromadné dekódování z výkazu**, kontrolní náhled před vložením, kopírování do Excelu, úprava pozice/ks, duplikace, posun, mazání a filtr,
- **Návrh**: ruční návrh i **Vložit výkaz…**, kontrolní náhled, hromadný přepočet a stejné akce nad řádky,
- **Záměny**: společná volba cílového výrobce **Ancon / Schöck**, tlačítko **Aktualizovat z Dekodéru**, přepočet celé tabulky a možnost ruční záměny,
- jednotlivý řádek Dekodéru lze dál převést do Záměn dvojklikem nebo tlačítkem **Převést do Záměn**,
- historické značení Schöck Dorn zůstává z bezpečnostních důvodů pouze v Dekodéru,
- při importu návrhu smykových trnů se hodnota výslovně zadaná v `kN/m` nepřebírá jako `kN/trn`,
- výpočtová pravidla a katalogové hodnoty Ancon / Leviat a Schöck se v 2.1.4 nemění,
- databáze AKCÍ se aktualizací nemění.

## TURTO 2.1.3

- nový návrh izolačních nosníků začíná s prázdnou tabulkou; řádek se vloží až tlačítkem **+ Přidat řádek**,
- také **Vymazat vše** ponechá návrh HIT skutečně bez řádků,
- v Dekodéru smykových trnů lze vybrat řádek a přímo zvolit, zda se má zaměnit za **Ancon** nebo **Schöck**,
- tlačítko **Převést do Záměn** přenese do záměny pozici, počet kusů, označení, výšku, spáru, beton a krytí,
- dvojklik na dekódovaný smykový trn používá stejnou volbu cílového výrobce,
- výpočtová pravidla a katalogové hodnoty Ancon / Leviat a Schöck se v 2.1.3 nemění,
- databáze AKCÍ se aktualizací nemění.

## Online aktualizace

Program používá `update_manifest.json`; aktuální updater načítá manifest přednostně přes GitHub API, aby nebyl závislý na zastaralé RAW cache. Z funkční verze TURTO 2.1.3 stačí v programu spustit **Aktualizace**; nabídne se verze **2.1.4** a stáhnou se pouze soubory potřebné pro aktuální vydání. Aktualizátor před nahrazením souborů vytváří lokální zálohu v `.update_backup`.

## Když se TURTO vůbec nespustí

Pokud je lokálně nainstalovaná verze, která spadne ještě před otevřením hlavního okna, nemůže se dostat k tlačítku **Aktualizace**. Pro tento stav je v kořeni repozitáře samostatná nouzová oprava:

1. Stáhněte aktuální ZIP repozitáře přes **Code → Download ZIP** a rozbalte jej.
2. Spusťte **`OPRAVIT_TURTO.bat`**.
3. Pokud se otevře výběr složky, vyberte svoji skutečnou instalační složku TURTO – tu, která obsahuje `app.pyw` nebo `Spustit_program.vbs`.
4. Oprava vytvoří zálohu stávající spouštěcí vrstvy a obnoví ověřený startovací základ 2.1.2. Po úspěšném spuštění pak použijte běžnou online aktualizaci.
5. **Databáze `actions.sqlite3` ani obsah uložených AKCÍ se nemění.**

Opravný nástroj zapisuje průběh do `recovery_2_1_2.log`. Pokud bootstrap naběhne, ale selže následný start runtime, úplný traceback se uloží do `startup_2_1_2.log` přímo v instalační složce TURTO.

## TURTO 2.1.2 – stabilizační základ

- návrat na ověřený startovací řetězec 2.1.0 po regresi 2.1.1,
- izolační nosníky HIT zůstávají na stávajícím výpočtovém jádře včetně M–V interakce,
- smykové trny mají vlastní **Dekodér / Návrh / Záměny**,
- aktivní jsou současné návrhové a záměnové tabulky Ancon / Leviat a Schöck Stacon,
- historické Schöck Dorn značení je pouze pomůcka Dekodéru a nevstupuje do automatického návrhu ani záměn.

---

## Původní přechod z v0.4.0 / v0.5.0 na GitHub základ

Historický GitHub základ byl verze 0.5.1. Jednorázový převod z velmi starých lokálních instalací zůstává v repozitáři jako **`00_INSTALOVAT_TURTO.bat`**.

Tento převod využívá existující funkční složku TURTO v0.4.0 nebo v0.5.0, zachová katalogová data a vytvoří zálohu měněných souborů. Pro současnou instalaci 2.x jej nepoužívejte jako opravný nástroj; při problému se startem použijte **`OPRAVIT_TURTO.bat`**.

## Důležité upozornění

Program je katalogová databázová a návrhová pomůcka. Nenahrazuje technické informace výrobce ani úplné statické posouzení. Před použitím ve výpočtu vždy ověřte celé označení, katalogové vydání, geometrické podmínky a zdrojové tabulky.
