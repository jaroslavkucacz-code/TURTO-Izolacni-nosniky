# Peikko 2.2.30 – rozsah, zdroje a audit tabulek

Tato aktualizace odděluje **rozpoznání označení**, **katalogovou referenci**,
**shodu se standardní tabulkovou konfigurací** a **omezené porovnání M/V**.
Nevydává úplný statický posudek a nepovoluje automaticky potvrzenou záměnu.

## Originální zdroje

| Dokument | Revize | SHA-256 originálního PDF |
|---|---|---|
| EBEA Technical Manual, Peikko Group | 004; 08/2023 | `1ea1abffe83a5c6e32b37287c5fba44d79ec63863f1dd17e93e5340846f80121` |
| TEBEA ETA 23/0525 | 01; 10. 2. 2025 | `9cabd5553b35636e03c91ed06ca0d45bef924bc4ada596129bda5fd5cf0d250d` |

EBEA: https://media.peikko.com/file/dl/i/OGas3A/Nous9DJNosZwZjufJk_Uiw/EBEA_Peikko_Group_004_Technical_Manual_Web.pdf?fv=5548

TEBEA: https://media.peikko.com/file/dl/i/cPI0Nw/75qMwAS9V0SMGRPKy9iGbg/ETA_23-0525_version-01_Peikko_TEBEA.pdf?fv=f80a

EBEA manuál je odkazovaný českou produktovou stránkou výrobce. Země-specifické
požadavky se tím nepovažují za automaticky ověřené. Nebyla importována neveřejná
databáze Peikko Designer ani provedena série jeho referenčních výpočtů.

## Extrakce a vizuální kontrola

Převzato z textové vrstvy originálních PDF, bez OCR, následně porovnáno se
zobrazenými tabulkami a jejich poznámkami. Skript
`tools/build_peikko_tables_2230.py` vyžaduje přesné SHA zdrojových souborů.
Neshodná revize vyžaduje novou kontrolu; nelze přepsat data jiným PDF naslepo.

| Rodina | Tabulky / tištěné stránky | Převzatá data |
|---|---|---|
| EBEA-100 | 3 a 4 / str. 15; geometrie str. 14 | 72 momentových/tuhostních a 126 smykových záznamů |
| EBEA E-100 | 6 a 7 / str. 17; geometrie str. 16 | 64 momentových/tuhostních a 112 smykových záznamů |
| EBEA-700 | 16 a 17 / str. 25; geometrie str. 24 | 108 momentových/tuhostních a 90 smykových záznamů |
| TEBEA | ETA A2.2, A3.1, A5.1, A5.2, A6.1 / str. 7, 8, 10, 11 | 57 hodnot součástí, nikoli celé sestavy |

Celkem 244 záznamů M/k, 328 záznamů V a 57 komponentových záznamů. Nejde
v žádném případě o 629 typů s kompletně schválenou únosností.

Databáze je standardní komprimované JSON: `peikko_technical_data.json.gz`.
Po rozbalení obsahuje přesné hodnoty, zdroj, stránku, tabulku a podmínky.
Komprese nezavádí runtime závislosti. Reprodukce vyžaduje pouze vývojářsky
PyMuPDF; aplikace používá standardní knihovnu Pythonu.

## Podmínky EBEA

Standardní D se nedoplňuje z Ds/Dt. D je třeba uvést v označení (`D200`) nebo
výslovně ve formuláři. Potvrzení standardní geometrie a krytí je při novém
výběru prázdné; samotné zadání D tedy neaktivuje úplné statické vyhovění.

Krytí nahoře/dole: 100 = 30/25; E-100 = 45/30; 700 = 30/30 mm. Přidané
izolace nad/pod nosnou část nezvyšují tabulkovou únosnost. L a počet smykových
součástí musejí odpovídat mezím konkrétní ohybové sestavy. Hodnoty jsou na
prvek, nikoli na metr. U příkladu L500 se nesmí zdvojnásobit tabulková únosnost
pro porovnání se silou na prvek. Přepočet zatížení na metr vyžaduje samostatnou
zatěžovací šířku, která se z L automaticky neodvozuje.

C25/30 a vyšší: hodnoty tabulek bez zvyšování. C20/25: součinitel 0,8 pro
únosnosti podle §1.2 na str. 7; není použit pro rotační tuhost k.

100 a E-100 přenášejí záporný moment a smyk obou znamének. 700 přenáší
moment obou znamének. Při NEd = 0 jsou porovnávány samostatné tabulkové meze
M a V; nenulové NEd je vždy blokované. Porovnání není kontrolou kotvení,
navazujícího betonu, přídavné výztuže, deformací, požáru ani národní přílohy.

**Zlaté kontrolní buňky:** při D200, C25/30, standardní geometrii:

- EBEA-100 4x10-2, ISO80: MRd 23 kNm/prvek, VRd 76 kN/prvek, k 2995 kNm/rad.
- EBEA E-100 4x10-3, ISO80: MRd 20, VRd 99, k 2334 ve stejných jednotkách.
- EBEA-700 VE1 4x10-3, ISO80: pro S11=120 je MRd 15; pro S11=370 je MRd 19;
  VRd 114 a k 1317. Čísla nejsou automatickým potvrzením položek e9/e10,
  které obsahují OQ a pouze Ds/Dt.
- EBEA-700, D180, ISO80: jedna smyková součást 33 kN, dvě 65 kN. Proto se
  používají přesné buňky, nikoli násobek zaokrouhlené jednotkové hodnoty.

## Neshody originálních zdrojů

1. EBEA tabulka 16 tiskne pro osové NRd jednotku `kNm/pcs`. Hodnota a
   tištěná jednotka jsou uchované, ale nejsou přepsané na kN odhadem.
   Interakce M+N zůstává vypnutá.
2. ETA A6.1 poslední řádek (průměr 14, ocel 1.4362) tiskne ISO `1` mm.
   Tento řádek není zařazen mezi použitelné údaje pro ISO120.

OQ, B2 a individuální sestavy jsou zachovány; jejich vliv není ignorován.
Netabulkové počty a průměry prutů nejsou dopočítávány lineárním poměrem.
Chybějící informace blokuje příslušné porovnání, nikoli celý technický přehled.

## Integrace a kompatibilita

Stejný catalog_id `peikko_syntax_1` a generation `syntax-1` zachovávají již
uložené akce 2.2.29. Nová data jsou v nehodnotících výsledcích (`kind=other`),
nikoli v automatickém návrhovém kontraktu moment/shear. Ochrana návrhu a
přijetí záměny zůstává aktivní i při přímém volání mimo UI.

PDF se stahuje pouze na explicitní požadavek. URL je HTTPS na media.peikko.com,
SHA je připnuté k ověřené revizi, zápis je atomický a změněné/neplatné PDF
se neotevře jako ověřený zdroj. Lokální umístění: `Katalogy/Peikko`.

## Ověření

`tools/verify_peikko_2230.py`: 33 testů včetně buněk, jednotek, S11, všech
14 původních příkladů, chybějících údajů, nepovolených konstrukčních variant,
uložení D a hashově ověřené PDF cache. `tools/verify_peikko_2230_runtime.py`:
instalace/oprava/idempotence, skutečné Tk okno, stálá viditelnost výsledků a
akčních tlačítek, předvýběr, zneplatnění při změně betonu, hromadné vložení,
centrální SQLite a původní ochrany HIT/Ancon. Windows/Linux výsledky jsou
součástí CI u příslušného commitu; neodvozují se z pouhého přepisu dokumentace.
