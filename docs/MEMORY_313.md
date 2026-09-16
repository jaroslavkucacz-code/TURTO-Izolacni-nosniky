# Paměť katalogů – 3.0.13

Profilování původní aplikace ukázalo přibližně 308 MiB živých objektů Pythonu.
Největší zbytečnou položkou byly sady tokenů u každého katalogového záznamu,
které vyhledávání nečetlo, a obrácený index tvořený velkými množinami.
Index se při spuštění sestavoval třikrát (základ + CXT AP + T-QP).

Nový engine sdílí pouze shodné neměnné řetězce; všechny měnitelné záznamy
zůstávají samostatné. Obrácený index ukládá indexy záznamů do array('I').
Rozšíření katalogů index zneplatní. Hlavní aplikace jej připraví jednou
po dokončení všech rozšíření, aby první překlep nezdržoval editor.
Samostatně používaný engine jej připraví při prvním fuzzy dotazu.

## Ověření

`tools/verify_memory_313.py` spouští dvě skutečná GUI v samostatných procesech
s izolovaným nastavením. Liší se pouze katalogový engine. Porovnává hash
všech katalogových hodnot a 213 sad výsledků vyhledávání včetně pořadí,
skóre, katalogových hodnot, aliasů, překlepů, betonu, preferovaného katalogu
a T-QP-VV1-REI120-H200-L300-5.0. Kontroluje také přidání/odebrání záznamu
po vytvoření indexu. Do distribuovaných dat nic nezapisuje.

Linux/Python 3.12, bez tracemalloc: klidové RSS 358,30 → 188,75 MiB,
po vyhledávání 376,19 → 206,32 MiB; start 12,61 → 6,36 s.
Měření je orientační pro dané prostředí, ne slib konkrétní paměti na všech PC.
Obě katalogové a výsledkové kontrolní sumy jsou shodné.

Windows CI navíc měří WorkingSetSize a PrivateUsage přímo uvnitř EXE.
Používá ověřený hostitel z vydaného balíčku 3.0.12 s aktuálními zdroji,
takže ověří i kompatibilitu online aktualizace s již distribuovaným EXE.
Výsledek ukládá do artefaktu Windows-EXE-verification/memory-313.json.
Samostatný test aktuálního EXE ověřuje bootstrap, AKCE, PDF/XLSX a restart
po aktualizaci. Nejde o umělé vyprázdnění pracovní sady procesu.
