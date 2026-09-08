# Changelog

## 2.2.1

Pokračování technického úklidu bez změny statických pravidel, katalogových hodnot nebo dat AKCÍ.

- obecný aktuální bootstrap místo recovery navázané na verzi 2.1.2,
- obecné diagnostické soubory `startup.log` a `recovery.log`,
- aktuální runtime marker `.turto_runtime_current.ok`,
- recovery používá stejný commit-pinned `app.pyw` a `updater.py` jako online manifest,
- updater nejprve vytvoří úplnou zálohu měněných souborů a při chybě provede rollback,
- `actions.sqlite3` je explicitně chráněný cíl,
- CI kontroluje manifest, bootstrap, runtime installer, recovery, rollback, SHA-256 a syntaxi.

## 2.2.0

Technický úklid a stabilizace bez změny statických pravidel nebo katalogových dat.

- stabilní vstupní hranice pro smykové trny a Schöck Dorn,
- jeden aktuální CI workflow,
- automatická validace release manifestu,
- odstranění historických build artefaktů z aktuální větve,
- přesun starého převodu v0.4/v0.5 do `legacy/`,
- zjednodušená dokumentace architektury a release procesu.

## 2.1.5

- archivní VRd pro historické Schöck Dorn SLD/SLD-Q a kompletní LD/LD-Q,
- odstranění `cnom Schöck` z Dekodéru,
- archivní VRd lze použít jako požadavek záměny za Ancon nebo současný Schöck Stacon.

## 2.1.4

- sjednocení workflow smykových trnů s izolačními nosníky,
- hromadné vložení z výkazu,
- společné akce nad řádky,
- hromadné Záměny z Dekodéru.

## 2.1.3

- návrh HIT začíná bez automatického prázdného řádku,
- převod vybraného smykového trnu z Dekodéru do Záměn,
- opravený updater používající GitHub API pro načtení manifestu.

## 2.1.2

Stabilizační startovací základ po regresi 2.1.1.
