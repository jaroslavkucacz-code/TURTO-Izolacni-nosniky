# Kontrola rozložení Peikko 2.2.30

První Windows CI odhalilo příliš nízkou výsledkovou plochu. Stejná chyba byla
reprodukována lokálně při menší virtuální obrazovce; nešlo o chybu tabulek.

Oprava přesouvá nadpis do posuvné vstupní části a používá vlastní kompaktní
styl kontextových tlačítek. Nemění styly HIT, Ancon ani ostatních pracovních
postupů. Výsledky a akční tlačítka se neposouvají společně s formulářem.

Regresní test nyní explicitně používá okno 1180 × 704 px a nadále požaduje
alespoň 80 px pro výsledky i viditelnost všech akčních řádků. Při selhání
vypíše geometrii rodičů. Tk, logy a SQLite fixture se uzavírají i při výjimce,
aby Windows cleanup nepřekryl původní chybu. Lokální kontrola a sestavovací
workflow prošly na obrazovce 1280 × 720 px.

Konečné výsledky Windows/Linux ověřuje CI konkrétního commitu. Údaje,
výpočtové podmínky a ochrana uživatelské databáze nejsou touto opravou měněny.
Aktualizační runtime obsahuje sedm souborů o celkové velikosti 82 323 B;
originální PDF se stahují až na výslovný požadavek uživatele.
