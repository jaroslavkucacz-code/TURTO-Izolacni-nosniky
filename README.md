# TURTO – Databáze izolačních nosníků

**Aktuální verze: 0.6.1**  
Vytvořil Ing. Jaroslav Kučera

Lokální Windows aplikace pro vyhledávání, porovnávání a projektové soupisy izolačních nosníků podle konkrétních katalogových vydání.

## První instalace

1. Na GitHubu zvolte **Code → Download ZIP**.
2. ZIP rozbalte do běžné zapisovatelné složky, např. `Dokumenty\\TURTO-Izolacni-nosniky`.
3. Spusťte `Spustit_program.vbs`.
4. Je potřeba běžný 64bitový Python pro Windows s Tkinterem. Další Python balíčky nejsou pro běh programu potřeba.

Od verze 0.6.1 má program v horní liště tlačítko **Aktualizace** a zároveň po spuštění tiše kontroluje `update_manifest.json` v tomto repozitáři. Při nové verzi stáhne jen soubory uvedené v manifestu, ověří jejich SHA-256 a po potvrzení je nahradí externím aktualizačním pomocníkem.

## Databáze 0.6.1

Program obsahuje 4 katalogová vydání, 3 výrobce, 79 produktových rodin a 283 687 jednoznačně volitelných katalogových kombinací.

- **Schöck Isokorb® T / XT** – CZ/2024.1, září 2024.
- **ISOPRO® 80 mm** – dodané vydání 2018 EN.
- **MAX FRANK Egcobox® M 80 mm** – International / ETA-19/0046, tabulky 2022-10-24.
- **MAX FRANK Egcobox® XL 120 mm** – International / ETA-19/0046, tabulky 2022-10-24.

U produktů je nově samostatně evidována **tloušťka izolantu** a tam, kde to katalog dovoluje jednoznačně určit, také **způsob tlakového přenosu**. U smykových prvků tak program rozlišuje varianty s tlakovými ložisky a varianty bez tlakových komponent.

## Našeptávač neúplného označení

Není nutné znát celé označení. Lze psát například:

- `xt kl m8 v2 220`
- `schok xt kll m8 v2 220`
- `isopro aipq 60`
- `vm 130`
- `mxl 50 v2 c35 h220`

Nabídka průběžně zobrazuje konkrétní katalogové možnosti, tloušťku izolantu, tlakový přenos a základní statické hodnoty. Program návrh nikdy automaticky nepotvrdí za uživatele.

## Katalogová data a zdrojové PDF

Pro malou velikost repozitáře jsou katalogová data uložena jako textové soubory `*.json.gz.b64`. Aplikace je transparentně rozbalí v paměti; při běžném používání nevznikají žádné pracovní databázové soubory.

Zdrojová PDF výrobců nejsou v GitHub repozitáři redistribuována. Datové záznamy ale zachovávají čísla zdrojových stran a identifikaci použitého vydání. Kontrolní skripty pro zdrojová PDF lze použít v interním vývojovém balíčku, pokud jsou originální katalogy vloženy do složky `sources`.

## Důležité upozornění

Program je katalogová databázová pomůcka. Nenahrazuje technické informace výrobce, úplné statické posouzení, kontrolu interakcí, statického systému, navazujících konstrukcí, geometrických podmínek ani zabudování. Před použitím ve výpočtu vždy ověřte celé označení, katalogové vydání a zdrojovou stranu.
