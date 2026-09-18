# Schöck T KL 2.0 – doložený archiv

Primární zdroj: [Technické informace Schöck Isokorb T, CZ/2023.1, duben 2023](https://www.schoeck.com/viewfile/8280/ARCHIV_Technicke_informace_Schoeck_Isokorb_T_pro_elezobetonove_konstrukce_Duben_2023__8280__.pdf).
SHA-256: `9b60590c4e8d91c5752da49506942ef1058e7eb14652037d01f19b9ea61ebf6c`.

- Str. 44 výslovně určuje generaci 2.0, M1–M12, V1/V2/VV1, REI120, CV1/CV2, rozsah výšek a délku 1000 mm.
- Str. 45 určuje statický systém a minimální výšku CV2 180 mm.
- Str. 46 a 47 obsahují použité momenty a smykové únosnosti pro beton ≥ C25/30. V programu je zachována dosavadní katalogová volba C25/30.
- CV1: H160–300 po 10 mm; CV2: H180–300 po 10 mm. Bez interpolace nebo extrapolace.
- Nezávisle porovnáno všech 336 momentových buněk a smykové třídy s [Dimenzačními tabulkami, duben 2023](https://www.schoeck.com/viewfile/8316/ARCHIV_Dimenza_ni_tabulky_Schoeck_Isokorb_Duben_2023__8316__.pdf), str. 11–12, SHA-256 `58710d33214d4c685b86781311b3d5481ef7809539886add7c75261cd204b335`. Řádky se shodují; výšky CV1/CV2 byly rozlišeny podle polohy sloupců a ověřeny na vyrenderovaných stránkách.
- Na str. 47 mají M10/CV1/H180 a H190 vytištěno `57,8` a `63,5` bez záporného znaménka. Stejná nejasnost je v dimenzačních tabulkách. Tyto dvě buňky × tři smykové třídy jsou vynechány. Žádná automatická oprava znaménka. Z 1008 kombinací je načteno 1002.

Data jsou novým samostatným katalogem, nevznikla přejmenováním generace 2.2. Stávající katalogy, zákaznický katalog stejného ID a snímky uložených akcí se nepřepisují. V přehledu Katalogy lze stáhnout celý původní dokument; dostupnost jeho PDF neznamená automatické načtení všech ostatních řad.

## Rozsah dodaného výkazu

Sedm řádků T KL 2.0, celkem 2311 ks, nyní odpovídá přesným záznamům. U CV1/H200 jsou momenty M2 −16,7; M3 −23,7; M4 −29,3; M5 −34,9; M6 −40,5; M8 −49,4 kNm/m. Smyk V1 pro M1–M7 je 61,8 a pro M8–M12 92,7 kN/m; V2 je 154,5; VV1 +92,7/−61,8 kN/m.

KL-U má v tomto archivu generaci 7.1 (str. 70); označení KL-U 2.0 zůstává neověřené. ZL je mezikus bez statické funkce, str. 135 (PDF str. 137), bez doložené generace 2.0. QP bez L nadále vyžaduje potvrzení skutečné délky; VV-V1 zůstává nejednoznačné. Tyto položky nejsou převáděny na jinou generaci.

Ověření: `tools/verify_archive_catalog_322.py` v reálné aplikaci a zabaleném Windows EXE: vlastní výkaz, rychlé zadání, indexy, vyloučené kombinace, skutečný přepočet účinků pro záměnu HIT, SQLite a opětovné otevření, PDF a XLSX. Test nedodává smyšlené únosnosti HIT.
