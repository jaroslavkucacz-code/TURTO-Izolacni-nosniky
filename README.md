# TURTO – Databáze izolačních nosníků

**Stabilní GitHub základ: 0.5.1**  
Vytvořil Ing. Jaroslav Kučera

Lokální Windows aplikace pro vyhledávání, porovnávání a projektové soupisy izolačních nosníků podle katalogových dimenzačních tabulek.

## Jednorázový přechod z v0.4.0 na GitHub verzi

Aktuální přechod využívá vaši existující složku **TURTO_Izolacni_nosniky_v0.4.0**. Díky tomu není nutné znovu přenášet velké katalogové soubory a během převodu se **nestahují žádné instalační části z internetu**.

1. Klikněte nahoře na zelené tlačítko **Code → Download ZIP**.
2. Stažený ZIP celý rozbalte do nové složky.
3. V rozbalené složce spusťte **`00_INSTALOVAT_TURTO.bat`**.
4. Pokud se otevře výběr složky, vyberte svoji stávající složku **`TURTO_Izolacni_nosniky_v0.4.0`**.
5. Převod nejprve ověří všechny nové programové soubory pomocí SHA-256, vytvoří zálohu změněných souborů v `.backup_pred_github_v0.5.1` a teprve potom je nahradí.
6. Katalogová data Schöck + ISOPRO i ostatní původní soubory zůstanou zachované.
7. Po dokončení se TURTO pokusí automaticky spustit přes stávající **`Spustit_program.vbs`**.

Je potřeba běžný 64bitový Python pro Windows s Tkinterem. Převod používá pouze standardní knihovny Pythonu.

### Jak poznám správný průběh

V konzoli se zobrazí přibližně:

```text
TURTO - převod v0.4.0 na GitHub verzi v0.5.1
Tento krok nestahuje instalační data z internetu.
...
  OK  app.pyw
  OK  catalog_engine.py
  OK  project_ui.py
  OK  autocomplete.py
  OK  updater.py
  OK  version.txt

HOTOVO. TURTO je ve verzi 0.5.1.
```

Pokud místo toho vidíte `Stahuji ... část 1/16`, spouštíte starou kopii repozitáře. Smažte ji a stáhněte ZIP znovu.

## Automatické aktualizace

Od verze 0.5.1 má program tlačítko **Aktualizace**. Další verze už nebude nutné celé stahovat znovu. Program načte `update_manifest.json` a stáhne pouze změněné soubory podle manifestu.

## Obsah stabilní verze 0.5.1

- kompletní databáze Schöck Isokorb® T / XT z použitého vydání CZ/2024.1,
- kompletní databáze ISOPRO® z dodaného katalogu 2018 EN,
- projektové soupisy,
- našeptávač neúplného označení a tolerance běžných překlepů,
- automatický aktualizační mechanismus.

**MAX FRANK Egcobox® M / XL zatím není součástí této stabilní základny.** Bude přidán jako první katalogová automatická aktualizace spolu s explicitním údajem o tloušťce izolantu a rozlišením smykových prvků s tlakovými ložisky / bez tlakových komponent.

## Důležité upozornění

Program je katalogová databázová pomůcka. Nenahrazuje technické informace výrobce ani úplné statické posouzení. Před použitím ve výpočtu vždy ověřte celé označení, katalogové vydání, geometrické podmínky a zdrojovou stránku.
