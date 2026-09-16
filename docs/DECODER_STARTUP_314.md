# Oprava dekodéru a spuštění 3.0.14

Rychlé zadání a plovoucí našeptávač volaly obecný katalogový resolver.
Přesné schémové rozpoznání T/XT/CXT z verzí 3.0.1 a 3.0.4 bylo navázané
především na hromadný import; globálně byl později opraven jen T-QP.
Například pro úplné XT-KL-M2-V1-REI120-CV35-H200-6.2 bez zdrojového záznamu
rychlý našeptávač nabízel ISOPRO. Test paměti 3.0.13 porovnával dva enginy
se stejnými adaptéry, proto tento rozdíl mezi cestami UI neodhalil.

`decoder_314.py` zapojuje přesné klasifikátory také do rychlého dekodéru
včetně vnějšího adaptéru HIT/Peikko. Neúplná explicitní označení vyhledává
pouze v odpovídajících záznamech Schöck a podle zadaných parametrů/betonu.
Sconnex a ostatní výrobci používají původní adaptéry. Nové výrobní únosnosti
se nevytvářejí; chybějící zdrojový záznam je hlášen, nikoli nahrazen odhadem.

`tools/verify_decoder_314.py` ověřuje 33 formátů na izolovaných TEST_ONLY
záznamech původního schématu, shodu rychlého/bulk/popup výsledku, reálné
psaní, klávesu Enter, tlačítka Dekódovat a přidat a Analyzovat, výběr z popupu,
uložení a načtení SQLite, nesprávný beton/V/VV/generaci a chybějící data.
Samostatně ověřuje skutečný vydaný T-QP záznam a zachování Sconnex/Egcobox.
Fixtures nejsou součástí distribuovaného katalogu.

`startup_window.py` je nový ověřený root payload. Nativní Windows okno má
vlastní message loop ve vlákně a nezakládá další Tk ani nemění default root.
Bootstrap jej otevře před kontrolou a opravou runtime. Hotové hlavní okno
jej zavře při prvním idle; chybová i normální ukončovací cesta jej uklidí.
Nejčasnější zpoždění samotného zavedení EXE Windows/antivirem nemůže okno
pokrýt. Čas prvního zobrazení měří Windows CI skutečným spuštěním EXE,
včetně odpovědi okna na zprávy během načítání a jeho automatického zavření.

Sestavení kopíruje všechny ověřené root payloady z manifestu, včetně
načítacího okna. Updater test simuluje starší instalaci bez tohoto souboru
 a ověřuje jeho přenos a restart. Kontrola úspory paměti 3.0.13 zůstává aktivní.
