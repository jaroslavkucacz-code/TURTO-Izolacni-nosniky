# TURTO – izolační nosníky a smykové trny

Vytvořil Ing. Jaroslav Kučera

**Aktuální vydání: TURTO 2.1.5**  
Produktové oblasti: **Izolační nosníky** + **Smykové trny**.

Lokální Windows aplikace pro práci s centrálními AKCEMI, dekódování výrobků, návrhy a katalogové záměny.

## TURTO 2.1.5

- historické **Schöck Dorn SLD / SLD-Q 40, 50, 60, 70, 80, 120 a 150** mají v Dekodéru archivní tabulkové `VRd` z oficiální technické informace Schöck 2019,
- kompletní historické **Schöck Dorn LD / LD-Q 16, 20, 22, 25 a 30** mají archivní `VRd` z technické informace Schöck 2017,
- archivní hodnoty se používají **bez interpolace**: výška se volí na nejbližší nižší tabulkovou hodnotu a spára na nejbližší vyšší,
- z Dekodéru bylo odstraněno pole **cnom Schöck**; referenční krytí je vlastností archivní tabulky a zobrazuje se u zdroje (`SLD: 30 mm`, `LD: 20 mm`),
- Dekodér archivních Schöck Dorn umožňuje také beton **C20/25**, který je v archivních tabulkách SLD samostatně uveden,
- krytí současného cílového Schöck se zadává až v **Záměnách**, kde skutečně vstupuje do výběru cílového Stacon,
- archivní `VRd` původního Dorn lze použít jako požadavek automatické záměny za **Ancon** nebo současný **Schöck Stacon**,
- samostatná historická označení komponent `Part A4 / Zn / S / P` zůstávají pouze informativní v Dekodéru, protože neurčují celý komplet trnu,
- výpočtové tabulky současných Ancon / Leviat a Schöck Stacon se nemění,
- databáze AKCÍ se aktualizací nemění.

## TURTO 2.1.4

Smykové trny používají stejný základní pracovní model jako izolační nosníky:

- **Dekodér**: jednotlivé zadání i **Hromadné dekódování z výkazu**, kontrolní náhled před vložením, kopírování do Excelu, úprava pozice/ks, duplikace, posun, mazání a filtr,
- **Návrh**: ruční návrh i **Vložit výkaz…**, kontrolní náhled, hromadný přepočet a stejné akce nad řádky,
- **Záměny**: společná volba cílového výrobce **Ancon / Schöck**, tlačítko **Aktualizovat z Dekodéru**, přepočet celé tabulky a možnost ruční záměny,
- jednotlivý řádek Dekodéru lze převést do Záměn dvojklikem nebo tlačítkem **Převést do Záměn**,
- při importu návrhu smykových trnů se hodnota výslovně zadaná v `kN/m` nepřebírá jako `kN/trn`.

## TURTO 2.1.3

- nový návrh izolačních nosníků začíná s prázdnou tabulkou; řádek se vloží až tlačítkem **+ Přidat řádek**,
- také **Vymazat vše** ponechá návrh HIT skutečně bez řádků,
- v Dekodéru smykových trnů lze vybrat řádek a přímo zvolit, zda se má zaměnit za **Ancon** nebo **Schöck**,
- tlačítko **Převést do Záměn** přenese do záměny pozici, počet kusů, označení, výšku, spáru a beton,
- dvojklik na dekódovaný smykový trn používá stejnou volbu cílového výrobce.

## Online aktualizace

Program používá `update_manifest.json`; aktuální updater načítá manifest přednostně přes GitHub API, aby nebyl závislý na zastaralé RAW cache. Z funkční verze TURTO 2.1.3 nebo novější stačí v programu spustit **Aktualizace**; nabídne se aktuální verze a stáhnou se pouze potřebné programové soubory. Aktualizátor před nahrazením souborů vytváří lokální zálohu v `.update_backup`.

## Když se TURTO vůbec nespustí

Pokud je lokálně nainstalovaná verze, která spadne ještě před otevřením hlavního okna, nemůže se dostat k tlačítku **Aktualizace**. Pro tento stav je v kořeni repozitáře samostatná nouzová oprava:

1. Stáhněte aktuální ZIP repozitáře přes **Code → Download ZIP** a rozbalte jej.
2. Spusťte **`OPRAVIT_TURTO.bat`**.
3. Pokud se otevře výběr složky, vyberte svoji skutečnou instalační složku TURTO – tu, která obsahuje `app.pyw` nebo `Spustit_program.vbs`.
4. Oprava vytvoří zálohu stávající spouštěcí vrstvy a obnoví ověřený startovací základ. Po úspěšném spuštění pak použijte běžnou online aktualizaci.
5. **Databáze `actions.sqlite3` ani obsah uložených AKCÍ se nemění.**

## Důležité upozornění

Program je katalogová databázová a návrhová pomůcka. Nenahrazuje technické informace výrobce ani úplné statické posouzení. Před použitím ve výpočtu vždy ověřte celé označení, katalogové vydání, geometrické podmínky a zdrojové tabulky.
