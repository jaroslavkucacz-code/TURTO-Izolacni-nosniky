from __future__ import annotations

"""Manufacturer-neutral inputs; verified legacy engines remain authoritative.

New designs select a STANDARD catalog geometry. Imported products never inherit
that assumption: their explicit dimensions and unresolved tokens remain binding.
"""
from itertools import product
import re
from peikko_technical import number, integer, data, preselect, reference, compare_loads, format_reference, format_comparison, DISCLAIMER
from peikko_thermal_breaks import decode_peikko

VERSION = '2.2.31'
FUNCTIONS = ('Konzola – M + V', 'Pouze smyk', 'Rohová konzola', 'Obousměrný moment')
DEFAULTS = dict(function=FUNCTIONS[0], height='200', insulation='80', concrete='C25/30',
    cover='Auto', moment='0', shear='0', axial='0', fire='Bez požadavku', basis='Na metr spoje',
    length='1000', spacing='', arrangement='Souvislá řada (a = L)', designation='',
    D='', s11='', material='Auto', family='EBEA', hit_type='Auto', geometry='0')


def common(raw):
    """Validate only shared engineering inputs; never alter caller-owned values."""
    q = {**DEFAULTS, **raw}
    if q['function'] not in FUNCTIONS:
        raise ValueError('Vyberte podporovanou funkci konstrukce.')
    for key, label in [('height','Výška desky'),('insulation','Izolant'),('length','Délka prvku')]:
        q[key] = integer(q[key], label)
    if q['insulation'] not in (80,120):
        raise ValueError('Podporovaný izolant je 80 nebo 120 mm.')
    q['concrete'] = re.sub(r'\s+', '', q['concrete']).upper()
    q['cover'] = None if q['cover'] == 'Auto' else integer(q['cover'],'Krytí')
    for key, label in [('moment','MEd'),('shear','VEd'),('axial','NEd')]:
        q[key] = number(q[key] or '0', label)
    if not any(q[k] for k in ('moment','shear','axial')):
        raise ValueError('Zadejte alespoň jednu nenulovou návrhovou sílu.')
    if q['function']=='Pouze smyk' and (q['moment'] or q['axial']):
        raise ValueError('Funkce Pouze smyk nepovoluje MEd ani NEd; změňte funkci nebo zatížení.')
    if q['basis'] not in ('Na metr spoje','Na jeden prvek'):
        raise ValueError('Neznámé jednotky zatížení.')
    if q['arrangement']=='Souvislá řada (a = L)':
        q['width'] = q['length']
    elif q['arrangement']=='Vlastní rozteč':
        q['width'] = number(q['spacing'],'Rozteč / zatěžovací šířka')
        if q['width'] < q['length']:
            raise ValueError('Rozteč nesmí být menší než délka prvku (překryv prvků).')
    else:
        raise ValueError('Vyberte souvislou řadu nebo vlastní rozteč.')
    if q['fire'] not in ('Bez požadavku','REI60','REI90','REI120'):
        raise ValueError('Neznámý požadavek na požární odolnost.')
    return q


def basis_note(q):
    return (f"Zadání: {q['basis']}; L = {q['length']} mm; "
            f"rozteč / zatěžovací šířka = {q['width']:g} mm ({q['arrangement']}).")


def peikko_candidates(raw):
    q = common(raw)
    model = {FUNCTIONS[0]:'100', FUNCTIONS[2]:'E-100', FUNCTIONS[3]:'700'}.get(q['function'])
    if q['family'] != 'EBEA':
        raise ValueError('TEBEA: dostupná ETA data jsou hodnoty součástí, nikoli celého nosníku. Návrh celého prvku zatím nelze potvrdit; katalogová data zůstávají přístupná.')
    if model is None:
        raise ValueError('Pro smykové řady Peikko dosud nejsou ověřené návrhové tabulky. Momentový EBEA-100 se za smykový prvek nezaměňuje.')
    if q['concrete'] not in ('C20/25','C25/30','C30/37'):
        raise ValueError('Vyberte beton z nabídky společného formuláře.')
    spec = data()['models'][model]
    if q['cover'] is not None and q['cover'] != spec['covers_mm'][0]:
        raise ValueError(f"Tato tabulka Peikko vyžaduje krytí nahoře/dole {spec['covers_mm'][0]}/{spec['covers_mm'][1]} mm; zadané krytí se nesmí ignorovat.")
    text = q['designation'].strip()
    if text:
        d = decode_peikko(text)
        if d is None or d.family != 'EBEA' or d.model != model:
            raise ValueError('Označení neodpovídá zvolené funkci / řadě. Vymažte pevné označení pro nový návrh.')
        # All known constraints remain strict; no fallback to a different type.
        for actual, expected, label in ((d.sw_mm,q['insulation'],'izolant'),(d.length_mm,q['length'],'délka'),
            (d.cover_mm,q['cover'],'krytí'),(d.concrete,q['concrete'],'beton')):
            if actual not in (None,'') and expected not in (None,'') and actual != expected:
                raise ValueError('Označení a formulář mají rozdílný '+label+'.')
        if any(x is not None and x != q['height'] for x in (d.ds_mm,d.dt_mm)):
            raise ValueError('Ds/Dt v označení neodpovídají výšce desky ve formuláři; ověřte geometrii.')
        D = q['D'] or d.standard_d_mm
        if D is None:
            raise ValueError('U převzatého výrobku není doložené standardní D. Doplňte jej v Pokročilých; Ds/Dt nejsou automaticky D.')
        if integer(D,'D') > q['height']:
            raise ValueError('Standardní D nesmí přesahovat výšku desky.')
        if d.standard_d_mm is None: text += ' D'+str(integer(D,'D'))
        if q['material']!='Auto' and d.material!=q['material']:
            raise ValueError('Označení a formulář mají rozdílné provedení výztuže.')
        if q['s11'] and d.s11_mm!=integer(q['s11'],'S11'):
            raise ValueError('Označení a formulář mají rozdílné S11.')
        r = reference(text, standard_d_mm=D, concrete=q['concrete'], geometry_confirmed=q['geometry']=='1')
        check = compare_loads(r,moment=q['moment'],shear=q['shear'],axial=q['axial'],
            basis='element' if q['basis']=='Na jeden prvek' else 'per_metre',tributary_width_mm=q['width'])
        rows = [dict(designation=r['designation'],reference=r,comparison=check)]
    else:
        # A NEW standard product is proposed, not a reverse lookup Ds/Dt -> D.
        D = integer(q['D'] or q['height'],'Standardní D')
        if D > q['height']:
            raise ValueError('Standardní D nesmí přesahovat výšku desky.')
        if D not in range(spec['min_D'],301,20):
            raise ValueError('Výška není přesný tabulkový rozměr. V Pokročilých zvolte doložené standardní D; program neinterpoluje.')
        materials = spec['materials'] if q['material']=='Auto' else (q['material'],)
        s11s = ((integer(q['s11'],'S11'),) if q['s11'] else (120,160,200)) if model=='700' else (None,)
        rows = []
        for material, s11 in product(materials,s11s):
            rows += preselect(model=model,standard_d_mm=D,insulation_mm=q['insulation'],length_mm=q['length'],
                material=material,concrete=q['concrete'],moment=q['moment'],shear=q['shear'],axial=q['axial'],
                s11_mm=s11,basis='element' if q['basis']=='Na jeden prvek' else 'per_metre',
                tributary_width_mm=q['width'],geometry_confirmed=True)
    results=[]
    for row in rows:
        check=row['comparison'];r=row['reference']
        status='Tabulkové meze splněny' if check['table_pass'] else 'Tabulkové meze překročeny'
        detail = basis_note(q)+'\n'
        if not text:
            detail += ('PŘEDPOKLAD NOVÉHO NÁVRHU: standardní katalogová geometrie; D = '+str(D)+
                       f" mm; horní/dolní krytí = {spec['covers_mm'][0]}/{spec['covers_mm'][1]} mm. "
                       'Před použitím ověřit shodu s detailem konstrukce.\n')
        if model=='700': detail += 'S11 výsledku je geometrická varianta, ne zaměnitelná únosnost pro libovolný detail.\n'
        if q['fire']!='Bez požadavku':
            status+='; požár k ověření'
            detail += 'Požadavek '+q['fire']+' je uložen; požár není automaticky potvrzen.\n'
        detail += format_reference(r)+format_comparison(check)
        results.append(dict(manufacturer='Peikko',designation=row['designation'],
            utilization=max(check['eta_M'],check['eta_V']),status=status,detail=detail,
            design_verified=False,reference=r,comparison=check))
    return sorted(results,key=lambda r:(-r['utilization'],r['designation']))


def leviat_candidates(raw, database):
    from hit_core import DirectionalActions
    q=common(raw)
    if database is None:
        raise ValueError('Data HIT nejsou načtena. V Pokročilých zvolte Načíst data HIT; existující databáze se nemění.')
    if q['concrete'] not in ('C20/25','C25/30','C30/37'):
        raise ValueError('Beton není podporován ověřenou databází HIT.')
    types = {FUNCTIONS[0]:('MVX','MVXL'),FUNCTIONS[1]:('ZVX','ZDX'),FUNCTIONS[3]:('DD',)}.get(q['function'])
    if types is None:
        raise ValueError('Rohové / speciální HIT řešte přes Pokročilé → Výkaz a speciální typy HIT. Není zde automatická geometrická záměna.')
    if q['hit_type']!='Auto':
        if q['hit_type'] not in types: raise ValueError('Vybraný typ HIT neodpovídá funkci konstrukce.')
        types=(q['hit_type'],)
    length_code={1000:100,500:50,333:33,250:25}.get(q['length'])
    if length_code is None: raise ValueError('Pro standardní HIT zvolte délku 1000, 500, 333 nebo 250 mm.')
    series='HP' if q['insulation']==80 else 'SP'
    # Native HIT capacities are per metre of connector, not per bay/spacing.
    if q['axial']:
        raise ValueError('Nenulové NEd není v tomto standardním adaptéru HIT posouzeno. Použijte odpovídající speciální návrh; síla nebude ignorována.')
    multiplier=1000/q['length'] if q['basis']=='Na jeden prvek' else q['width']/q['length']
    m,v,n=(number(q[k]*multiplier,k) for k in ('moment','shear','axial'))
    actions=DirectionalActions(m_pos=max(m,0),m_neg=max(-m,0),v_pos=max(v,0),v_neg=max(-v,0),n_pos=max(n,0),n_neg=max(-n,0))
    covers=(q['cover'],) if q['cover'] is not None else ((30,) if q['function']==FUNCTIONS[1] else (30,35,50))
    results=[]; seen=set(); errors=[]
    for typ,cover in product(types,covers):
        found,error,_info=database.proposal_candidates(typ,series,q['height'],cover,q['concrete'],actions,{length_code},False,load_distance_x=0)
        if error: errors.append(error)
        for c in found:
            if c.concrete!=q['concrete'] or c.series!=series or c.height!=q['height'] or c.cover!=cover or c.physical_length_mm!=q['length']: continue
            if c.connection_type not in types: continue
            if c.suffix in ("OU","OD","WU","WD"): continue  # geometric offsets only; diameter suffixes remain valid
            if q['designation'].strip() and c.designation.upper()!=q['designation'].strip().upper(): continue
            if c.designation in seen: continue
            seen.add(c.designation)
            detail=(basis_note(q)+f'\nKrytí výsledku: {c.cover} mm; beton: {c.concrete}.\n'+
                f'Použit původní návrhový modul HIT; využití {100*c.utilization:.1f} %.\n'+
                f'MEd {m:g} kNm/m; VEd {v:g} kN/m; NEd {n:g} kN/m.\n'+
                f'Zdroj: {database.source_document}; strana {c.page}.\n'+c.mode+'\n'+c.source_note)
            status='Vyhovuje výpočtu HIT'
            if q['fire']!='Bez požadavku':
                status+='; požár k ověření';detail+='\nPožadavek '+q['fire']+' uložen, požár není tímto výpočtem potvrzen.'
            results.append(dict(manufacturer='Leviat',designation=c.designation,utilization=c.utilization,status=status,
                detail=detail,design_verified=False,candidate=c))
    if not results and errors: raise ValueError('\n'.join(dict.fromkeys(errors)))
    return sorted(results,key=lambda r:(-r['utilization'],r['designation']))


def calculate(raw,manufacturer,database=None):
    if manufacturer=='Peikko': return peikko_candidates(raw)
    if manufacturer=='Leviat': return leviat_candidates(raw,database)
    raise ValueError('Pro tohoto výrobce není dostupný návrhový adaptér.')
