# TURTO – Databáze izolačních nosníků

**Stabilní GitHub verze: 0.5.1**  
Vytvořil Ing. Jaroslav Kučera

Lokální Windows aplikace pro vyhledávání, porovnávání a projektové soupisy izolačních nosníků podle katalogových dimenzačních tabulek.

## První instalace

1. Klikněte nahoře na zelené tlačítko **Code** a zvolte **Download ZIP**.
2. Stažený ZIP celý rozbalte.
3. V rozbalené složce spusťte **`INSTALOVAT_TURTO.bat`**.
4. Instalátor stáhne ověřený balíček 0.5.1 z tohoto repozitáře, zkontroluje SHA-256 a rozbalí program do `Dokumenty\TURTO-Izolacni-nosniky`.
5. Program se pokusí spustit automaticky. Později jej spouštějte přes **`Spustit_program.vbs`** v cílové složce.

Je potřeba běžný 64bitový Python pro Windows s Tkinterem. Instalátor používá pouze standardní knihovny Pythonu.

## Automatické aktualizace

Od této základny má program tlačítko **Aktualizace**. Další verze už není nutné celé stahovat znovu. Program načte `update_manifest.json`, stáhne pouze změněné soubory, ověří jejich SHA-256 a následně je bezpečně nahradí externím aktualizačním pomocníkem.

## Obsah stabilní verze 0.5.1

- kompletní databáze Schöck Isokorb® T / XT z použitého vydání CZ/2024.1,
- kompletní databáze ISOPRO® z dodaného katalogu 2018 EN,
- projektové soupisy,
- našeptávač neúplného označení a tolerance běžných překlepů,
- automatický aktualizační mechanismus.

**MAX FRANK Egcobox® M / XL zatím není součástí této stabilní základny.** Bude přidán jako první katalogová automatická aktualizace spolu s explicitním údajem o tloušťce izolantu a rozlišením smykových prvků s tlakovými ložisky / bez tlakových komponent.

## Kontrola instalačního balíčku

SHA-256 instalačního ZIPu 0.5.1:

`38640f4cff62be037c8711641c3dbbf68c6198e7744278c3ca61b0812d36a9bc`

## Důležité upozornění

Program je katalogová databázová pomůcka. Nenahrazuje technické informace výrobce ani úplné statické posouzení. Před použitím ve výpočtu vždy ověřte celé označení, katalogové vydání, geometrické podmínky a zdrojovou stránku.
