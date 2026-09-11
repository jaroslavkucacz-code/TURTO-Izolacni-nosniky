from __future__ import annotations

"""Reviewed manufacturer table lookup, NOT approval of a structural connection.

Reference data, configuration matching and limited load comparisons are separate.
Nothing here enables automated substitutions or adds 'moment/shear' capacities to
legacy project contracts. Exact table rows only: no interpolation, no bar scaling.
"""
from functools import lru_cache
import json
import gzip
import math
from pathlib import Path
import re
from typing import Any

from peikko_thermal_breaks import decode_peikko, DecodedPeikko

DATA_VERSION = '2.2.30'
DISCLAIMER = ('Tabulkové porovnání není úplné statické posouzení ani potvrzená záměna. '
              'Ověřit národní podmínky, kotvení, doplňkovou výztuž, uspořádání, '
              'navazující konstrukce a mezní stav použitelnosti. Požár zde není posuzován.')
CONCRETES = ('C20/25','C25/30','C30/37','C35/45','C40/50','C45/55','C50/60',
             'C55/67','C60/75','C70/85','C80/95','C90/105')
MATERIALS = {
    'RS': 'Třením svařované provedení; korozní odolnost III.',
    'VE1': 'Nerezové provedení; korozní odolnost III.',
    'VE2': 'Nerezové provedení; korozní odolnost IV.',
}

@lru_cache(maxsize=1)
def data() -> dict:
    raw = Path(__file__).with_name('peikko_technical_data.json.gz').read_bytes()
    result = json.loads(gzip.decompress(raw).decode('utf-8'))
    if result.get('schema_version') != 1 or result.get('data_version') != DATA_VERSION:
        raise ValueError('Nekompatibilní technická databáze Peikko.')
    return result


def number(value: Any, label: str) -> float:
    if isinstance(value, bool):
        raise ValueError(label + ': zadejte konečné číslo.')
    try:
        out = float(str(value).strip().replace(',', '.'))
    except (ValueError, TypeError):
        raise ValueError(label + ': zadejte číslo.') from None
    if not math.isfinite(out):
        raise ValueError(label + ': zadejte konečné číslo.')
    return out


def integer(value: Any, label: str, *, minimum: int = 1) -> int:
    out = number(value, label)
    if out != int(out) or out < minimum:
        raise ValueError(label + f': zadejte celé číslo >= {minimum}.')
    return int(out)


def reinforcement_parts(d: DecodedPeikko) -> dict:
    match = re.fullmatch(r'(\d+)x(\d+)-(\d+)', d.reinforcement)
    if d.family != 'EBEA' or not match:
        return {}
    n, diameter, count = map(int, match.groups())
    return dict(bending_count=n,diameter_mm=diameter,shear_count=count,
        shear_label='smykové desky' if d.model in ('100','E-100','700') else 'smykové součásti (syntax)')


def reference(text: str, *, standard_d_mm=None, concrete: str | None = None,
              geometry_confirmed: bool = False) -> dict:
    d = decode_peikko(text)
    if d is None:
        raise ValueError('Zadejte označení EBEA/TEBEA.')
    explicit_d = getattr(d, 'standard_d_mm', None)
    chosen_d = integer(standard_d_mm, 'Standardní D') if standard_d_mm not in (None, '') else explicit_d
    if explicit_d is not None and chosen_d != explicit_d:
        raise ValueError('D ve formuláři odporuje D v označení.')
    chosen_concrete = re.sub(r'\s+', '', str(concrete or d.concrete or '')).upper()
    if d.concrete and chosen_concrete != d.concrete:
        raise ValueError('Beton formuláře/akce odporuje betonu v označení.')
    out = dict(designation=d.canonical,family=d.family,model=d.model,standard_d_mm=chosen_d,
        concrete=chosen_concrete,parameters=d.parameters,reinforcement=reinforcement_parts(d),
        material_description=MATERIALS.get(d.material,''),bending=None,shear=None,
        MRd=None,VRd=None,k=None,configuration_matched=False,design_verified=False,
        blockers=[],warnings=[],source='tebea_eta01' if d.family=='TEBEA' else 'ebea_004')
    errors=out['blockers']; warnings=out['warnings']
    if d.family == 'TEBEA':
        errors.append('Dostupné hodnoty ETA jsou hodnoty SOUČÁSTÍ, nikoli celého typu TEBEA.')
        out['component_rows'] = data()['tebea_components']
        return out
    spec = data()['models'].get(d.model)
    if spec is None:
        errors.append('Pro tuto řadu zatím nejsou přepsané a ověřené tabulky; nevytváří se odhad.')
        return out
    out['covers_mm'] = spec['covers_mm']
    if chosen_d is None:
        errors.append('Chybí standardní D; Ds/Dt se na D automaticky nepřevádějí.')
    elif chosen_d not in range(spec['min_D'],301,20):
        errors.append('D není přesný tabulkový řádek této řady; bez interpolace.')
    if chosen_concrete not in CONCRETES:
        factor = None
        errors.append('Chybí podporovaná třída betonu (C20/25 nebo vyšší standardní třída).')
    else:
        factor = 0.8 if chosen_concrete=='C20/25' else 1.0
    out['concrete_factor'] = factor
    if factor == 0.8:
        warnings.append('Únosnosti redukovány 0,8 pro C20/25 podle §1.2, str. 7; tuhost k není násobena tímto součinitelem.')
    if d.material not in spec['materials']:
        errors.append('Chybějící/nepodporované provedení výztuže pro tuto tabulkovou řadu.')
    if d.sw_mm not in (80,120):
        errors.append('Tabulky zahrnují pouze izolant 80/120 mm; chybějící údaj se nedoplňuje.')
    if d.variant:
        errors.append('Varianta '+d.variant+': účinek na tabulkovou únosnost není doložen.')
    if d.oq:
        errors.append('OQ: význam a vliv na konkrétní výrobek nejsou doloženy.')
    if d.unknown_text:
        errors.append('Nerozpoznané údaje: '+d.unknown_text)
    if not out['reinforcement']:
        errors.append('Chybí rozložitelný kód výztuže n×Ø-počet smykových součástí.')
    if d.cover_mm is not None and d.cover_mm != spec['covers_mm'][0]:
        errors.append('Zadané horní krytí neodpovídá předpokladům tabulky.')
    if d.ds_mm and d.dt_mm and d.ds_mm!=d.dt_mm:
        errors.append('Ds a Dt se liší; standardní geometrii nelze automaticky přiřadit.')
    if chosen_d is not None and any(x is not None and x<chosen_d for x in (d.ds_mm,d.dt_mm)):
        errors.append('D nesmí přesahovat zadané Ds/Dt.')
    if geometry_confirmed is not True:
        errors.append('Nepotvrzena standardní geometrie, poloha prutů a horní/dolní krytí dle tabulky.')
    s11_group=None
    if d.model=='700':
        if d.s11_mm in (120,160): s11_group=d.s11_mm
        elif d.s11_mm is not None and 200<=d.s11_mm<=430: s11_group=200
        else: errors.append('S11 musí být tabulkové 120/160 nebo v doloženém pásmu 200–430 mm. Bez interpolace.')
        warnings.append('Tabulka 16 tiskne u osové NRd jednotku kNm/pcs; automatické porovnání M+N je proto blokováno.')
    elif d.s11_mm is not None:
        errors.append('S11 není parametr standardní tabulky této řady; zvláštní provedení vyžaduje ověření.')
    parts=out['reinforcement']
    if chosen_d is not None and parts:
        candidates=[r for r in data()['bending'] if r['model']==d.model and r['D']==chosen_d
                    and r['n']==parts['bending_count'] and r['diameter']==parts['diameter_mm']
                    and (d.model!='700' or r['S11_group']==s11_group)]
        if candidates:
            row=dict(candidates[0]);out['bending']=row
            out['MRd']=row['MRd']*factor if factor is not None else None
            out['k']=row['k']
            if not row['shear_min']<=parts['shear_count']<=row['shear_max']:
                errors.append('Počet smykových součástí nepatří k tabulkové sestavě ohybové výztuže.')
            if d.length_mm is None or not row['Lmin']<=d.length_mm<=1200 or d.length_mm%50:
                errors.append(f"Délka musí být {row['Lmin']}–1200 mm v kroku 50 mm pro tuto sestavu.")
        else:
            errors.append('Ohybová sestava není v ověřené tabulce: počet/průměr/D/S11. Bez přepočtu poměrem prutů.')
        candidates=[r for r in data()['shear'] if r['model']==d.model and r['D']==chosen_d
                    and r['iso']==d.sw_mm and r['shear_count']==parts['shear_count']]
        if candidates:
            out['shear']=dict(candidates[0]);out['VRd']=candidates[0]['VRd']*factor if factor is not None else None
        else: errors.append('Smyková sestava není v ověřené tabulce pro zadané D/ISO/počet.')
    if d.fire_rating:
        warnings.append(d.fire_rating+': načtené označení není ověřením požární odolnosti.')
    out['blockers']=list(dict.fromkeys(errors))
    out['configuration_matched']=not out['blockers'] and out['MRd'] is not None and out['VRd'] is not None
    return out


def compare_loads(report: dict, *, moment, shear, axial=0, basis='element', tributary_width_mm=None) -> dict:
    """Only signed ULS M,V in the directions shown by the selected standard model.

    Per-metre input requires an EXPLICIT tributary width, never inferred from L.
    'table_pass' is NOT a full design state and is never sent to substitution code.
    """
    if not report.get('configuration_matched'):
        raise ValueError('Porovnání nelze provést: '+ '; '.join(report.get('blockers', [])))
    m=number(moment,'MEd');v=number(shear,'VEd');n=number(axial,'NEd')
    if n!=0:
        raise ValueError('Nenulové NEd vyžaduje samostatné doložené posouzení; M+N není v této verzi aktivní.')
    if basis=='per_metre':
        width=number(tributary_width_mm,'Zatěžovací šířka na jeden prvek [mm]')
        if width<=0: raise ValueError('Zatěžovací šířka musí být kladná; není automaticky rovna délce L.')
        m*=width/1000;v*=width/1000
    elif basis!='element': raise ValueError('Neznámá jednotková základna zatížení.')
    if not all(math.isfinite(x) for x in (m,v)): raise ValueError('Přepočet zatížení je mimo číselný rozsah.')
    if m==0 and v==0: raise ValueError('Zadejte alespoň jednu nenulovou návrhovou hodnotu MEd/VEd.')
    if report['model'] in ('100','E-100') and m>0:
        raise ValueError('Tato řada přenáší záporný moment; kladné MEd nelze přeznačit absolutní hodnotou.')
    eta_m=abs(m)/report['MRd'];eta_v=abs(v)/report['VRd']
    return dict(MEd_per_element=m,VEd_per_element=v,eta_M=eta_m,eta_V=eta_v,
                table_pass=eta_m<=1 and eta_v<=1,design_verified=False,disclaimer=DISCLAIMER,
                input_basis=basis,tributary_width_mm=number(tributary_width_mm,'Zatěžovací šířka') if basis=='per_metre' else None)


def preselect(*, model, standard_d_mm, insulation_mm, length_mm, material, concrete,
              moment, shear, axial=0, s11_mm=None, basis='element',tributary_width_mm=None,
              geometry_confirmed=False) -> list[dict]:
    """Exact catalogue configurations only; never substitute an existing custom row."""
    if model not in data()['models']: raise ValueError('Tabulkový předvýběr: EBEA-100, EBEA-E100 nebo EBEA-700.')
    D=integer(standard_d_mm,'D');iso=integer(insulation_mm,'ISO');length=integer(length_mm,'L')
    concrete=re.sub(r'\s+','',str(concrete)).upper()
    if concrete not in CONCRETES: raise ValueError('Nepodporovaná třída betonu; jiné betony se nenabízejí.')
    if material not in data()['models'][model]['materials']: raise ValueError('Nepodporované provedení výztuže.')
    if iso not in (80,120): raise ValueError('Tabulkový předvýběr vyžaduje ISO 80 nebo 120 mm.')
    if geometry_confirmed is not True: raise ValueError('Potvrďte předpoklady standardní tabulkové geometrie a krytí.')
    # Validate loads even if no geometrical candidates exist.
    for value,label in ((moment,'MEd'),(shear,'VEd'),(axial,'NEd')): number(value,label)
    if number(axial,'NEd')!=0: raise ValueError('Nenulové NEd není v tabulkovém předvýběru podporováno.')
    if number(moment,'MEd')==0 and number(shear,'VEd')==0: raise ValueError('Zadejte nenulové MEd/VEd.')
    if model in ('100','E-100') and number(moment,'MEd')>0: raise ValueError('Tato řada vyžaduje záporný moment.')
    if basis not in ('element','per_metre'): raise ValueError('Neznámá jednotková základna.')
    if basis=='per_metre' and number(tributary_width_mm,'Zatěžovací šířka')<=0: raise ValueError('Zatěžovací šířka musí být kladná.')
    if model=='700' and (s11_mm in (None,'') or not (integer(s11_mm,'S11') in (120,160) or 200<=integer(s11_mm,'S11')<=430)):
        raise ValueError('S11: tabulkové hodnoty jsou 120, 160 a pásmo 200–430 mm.')
    found=[];seen=set()
    for row in data()['bending']:
        if row['model']!=model or row['D']!=D: continue
        for sc in range(row['shear_min'],row['shear_max']+1):
            name='EBEA-'+model.replace('E-','E')+f' {material} {row["n"]}x{row["diameter"]}-{sc} D{D} SW{iso} L{length}'
            if model=='700':
                if s11_mm in (None,''): raise ValueError('Pro EBEA-700 zadejte S11.')
                name+=f' S11={integer(s11_mm,"S11")}'
            if name in seen: continue
            seen.add(name)
            r=reference(name,concrete=concrete,geometry_confirmed=True)
            if not r['configuration_matched']: continue
            check=compare_loads(r,moment=moment,shear=shear,axial=axial,basis=basis,tributary_width_mm=tributary_width_mm)
            if check['table_pass']: found.append(dict(designation=name,reference=r,comparison=check))
    return sorted(found,key=lambda x:(-max(x['comparison']['eta_M'],x['comparison']['eta_V']),x['designation']))


def fmt(value):
    return '—' if value is None else f'{value:g}'.replace('.',',')


def format_reference(report: dict) -> str:
    source=data()['sources'][report['source']]
    lines=[report['designation'],'KATALOGOVÁ DATA – nikoli potvrzená únosnost celé konkrétní dodávky',
           f"Zdroj: {source['title']}, {source['revision']}",f"Rozsah: {source['country_scope']}"]
    parts=report['reinforcement']
    if parts: lines.append(f"Výztuž: {parts['bending_count']} × Ø{parts['diameter_mm']} mm; {parts['shear_count']} × {parts['shear_label']}.")
    if report.get('material_description'): lines.append(report['material_description'])
    if report['family']=='TEBEA':
        lines.append('Hodnoty níže jsou na JEDNU SOUČÁST. Bez přiřazení sestavy, počtu, geometrie a modelu nejde o MRd/VRd celého nosníku.')
        for c in report.get('component_rows',[]):
            identity=', '.join(f'{k}={v}' for k,v in c.items() if k not in ('source','table','page','kind','unit','full_connector','value'))
            lines.append(f"ETA {c['table']}, str. {c['page']} | {c['kind']} | {identity} | {fmt(c['value'])} kN/součást")
        for issue in data()['issues']:
            if issue['source']=='tebea_eta01': lines.append('Neshoda zdroje: '+issue['issue'])
    else:
        lines += [f"Standardní D: {fmt(report['standard_d_mm'])} mm (ne automaticky Ds/Dt).",
                  'Beton zadání: '+(report['concrete'] or 'neuveden')]
        if report.get('covers_mm'):
            lines.append(f"Předpoklad krytí nahoře/dole: {report['covers_mm'][0]}/{report['covers_mm'][1]} mm.")
        for key,label,unit in [('MRd','|MRd|','kNm/prvek'),('VRd','|VRd|','kN/prvek'),('k','Rotační tuhost k','kNm/rad na prvek')]:
            lines.append(label+': '+fmt(report.get(key))+' '+unit)
        for key in ('bending','shear'):
            row=report.get(key)
            if row: lines.append(f"Použitá tabulka {row['table']}, str. {row['page']}; původní řádek D={row['D']} mm.")
        if report.get('bending',{} ) and 'NRd_source_value' in report['bending']:
            row=report['bending']
            lines.append(f"NRd v originálu: {row['NRd_source_value']} {row['NRd_source_unit']} (tištěná jednotka vyžaduje potvrzení; nepoužito ve výpočtu).")
    if report['blockers']:
        lines += ['','NEPOTVRZENÁ KONKRÉTNÍ KONFIGURACE:']+['• '+x for x in report['blockers']]
    else: lines += ['','Konfigurace odpovídá ověřenému tabulkovému výběru za potvrzených předpokladů.']
    if report['warnings']: lines += ['','Upozornění:']+['• '+x for x in report['warnings']]
    lines+=['',DISCLAIMER,'Zdrojové PDF: '+source['filename'], 'SHA-256: '+source['sha256']]
    return '\n'.join(lines)


def format_comparison(check: dict) -> str:
    return ('\n\nPOROVNÁNÍ NÁVRHOVÝCH SIL S TABULKOU\n'+
            ('Vstup na metr spoje; zatěžovací šířka '+fmt(check['tributary_width_mm'])+' mm.\n' if check.get('input_basis')=='per_metre' else 'Vstup na jeden prvek.\n')+
            f"MEd = {fmt(check['MEd_per_element'])} kNm/prvek; VEd = {fmt(check['VEd_per_element'])} kN/prvek\n"
            f"|MEd|/|MRd| = {fmt(100*check['eta_M'])} %; |VEd|/|VRd| = {fmt(100*check['eta_V'])} %\n"+
            ('Tabulkové meze nepřekročeny.' if check['table_pass'] else 'TABULKOVÁ ÚNOSNOST PŘEKROČENA.')+
            '\n'+DISCLAIMER)
