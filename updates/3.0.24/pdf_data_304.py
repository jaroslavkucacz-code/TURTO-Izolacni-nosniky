from __future__ import annotations

"""PDF export from live structured AKCE rows, never translated tree headings.
Preserves selected targets, directional per-element checks, missing values,
review state, and the distinction between identification, design and substitution.
No source/project data are modified by collection or rendering.
"""
from copy import deepcopy
from functools import wraps
import io
import logging
import math
from pathlib import Path

VERSION = '3.0.4'
LOG = logging.getLogger(__name__)
KEYS = ('m_pos','m_neg','n_pos','n_neg','v_pos','v_neg')
LABELS = dict(zip(KEYS,('M+','M−','N+','N−','V+','V−')))


def number(value):
    if isinstance(value,bool):
        return None
    try:
        n=float(str(value).strip().replace('−','-').replace(',','.'))
        return n if math.isfinite(n) else None
    except (ValueError,TypeError):
        return None


def fmt(value, digits=1):
    n=number(value)
    return '—' if n is None else f'{n:.{digits}f}'.replace('.',',')


def pct(value):
    n=number(value)
    return '—' if n is None else fmt(n*100)+' %'


def _dict(value):
    return value if isinstance(value,dict) else {}


def _notes(*groups):
    return list(dict.fromkeys(str(s) for g in groups for s in (g if isinstance(g,(list,tuple)) else [g]) if s not in (None,'','—')))


def _catalog_source(snapshot):
    pages=snapshot.get('source_pages') or []
    return ' • '.join(str(x) for x in (snapshot.get('source_filename'),snapshot.get('catalog_edition'),
                 ('str. '+', '.join(map(str,pages))) if pages else '') if x)


def _selected(mapping):
    target_id=mapping.get('selected_target_id')
    if target_id in (None,''):
        return {}
    hits=[x for x in mapping.get('targets',[]) if isinstance(x,dict) and str(x.get('id'))==str(target_id)]
    return deepcopy(hits[0]) if len(hits)==1 else {}


def _validate_checks(target, actions, meta):
    errors=[]
    if not target or not target.get('designation'):
        return ['Chybí jednoznačně vybraná cílová varianta; návrh znovu přepočítejte.']
    for k in ('height_mm','length_mm','cover_mm'):
        if number(target.get(k)) is None or number(target.get(k))<=0:
            errors.append('Cílová varianta nemá platný údaj '+k+'.')
    for source_key,target_key in (('target_height_mm','height_mm'),('target_cover_mm','cover_mm'),('target_insulation_mm','target_insulation_mm')):
        expected=number(meta.get(source_key)); actual=number(target.get(target_key))
        if expected is not None and (actual is None or expected!=actual):
            errors.append('Parametry záměny neodpovídají aktuálnímu zdroji: '+source_key+'.')
    if meta.get('target_concrete') and target.get('concrete')!=meta['target_concrete']:
        errors.append('Změnil se beton; návrh je nutné přepočítat.')
    if number(target.get('source_length_mm'))!=number(meta.get('source_length_mm')):
        errors.append('Změnila se délka zdroje; návrh je nutné přepočítat.')
    checks=target.get('checks')
    checks=checks if isinstance(checks,list) else []
    active={LABELS[k]:(number(actions.get(k)), 'kNm/prvek' if k[0]=='m' else 'kN/prvek')
            for k in KEYS if number(actions.get(k)) is not None and number(actions[k])>1e-9}
    if not active:
        errors.append('Chybí nenulové referenční účinky; nelze potvrdit nulové využití.')
    for label,(required,unit) in active.items():
        hits=[c for c in checks if isinstance(c,dict) and str(c.get('label')).replace('-','−')==label]
        if len(hits)!=1:
            errors.append('Chybí směrová kontrola '+label+'.'); continue
        c=hits[0]; req,cap,eta=[number(c.get(k)) for k in ('requirement','capacity','eta')]
        if (req is None or cap is None or cap<=0 or eta is None or c.get('unit')!=unit
                or not math.isclose(req,required,rel_tol=1e-8,abs_tol=1e-8)
                or not math.isclose(eta,req/cap,rel_tol=1e-8,abs_tol=1e-8)):
            errors.append('Neúplná nebo neaktuální kontrola '+label+'; návrh přepočítejte.')
    total=number(target.get('utilization'))
    etas=[number(c.get('eta')) for c in checks if isinstance(c,dict)]
    interaction=number(target.get('interaction_utilization'))
    lower=max([n for n in [*etas,interaction] if n is not None]+[0])
    if total is None or total<0 or total+1e-8<lower:
        errors.append('Chybí platné celkové využití vybrané varianty.')
    return errors


def iso_substitution_rows(owner):
    import substitution_workspace as sub
    rows=[]
    project=getattr(owner,'project',None)
    for raw in getattr(project,'rows',[]):
        if not isinstance(raw,dict):
            continue
        import infill
        if infill.dimensions(raw):
            rows.append(infill.report_row(owner, raw))
            continue
        mapping=_dict(raw.get('mapping')); snap=_dict(raw.get('snapshot'))
        # A scoped AKCE export includes the section, not an accidental selection
        # in a Treeview. It must work even when a different tab is active.
        payload,_=owner._payload(raw)
        meta=deepcopy(sub.source_metadata(raw))
        source_actions,warnings=sub.source_element_actions(raw)
        actions=sub.action_values(source_actions)
        reviewed=sub.review_state(raw,meta,warnings)
        target=_selected(mapping)
        status=str(payload.get('status') or 'NEPOSOUZENO')
        issues=_validate_checks(target,actions,meta) if mapping.get('status') in {'ok','review'} or target else []
        if mapping.get('status') in {'ok','review'} and not target:
            issues=_notes(issues,'Uložená záměna nemá vybraný cílový prvek.')
        if issues:
            status='NEPOSOUZENO – PŘEPOČÍTAT'
            # Preserve the last chosen name and dimensions for diagnostics, but
            # never display stale checks as a successful current calculation.
            target['checks']=[]; target['utilization']=None; target['interaction_utilization']=None
        elif target and number(target.get('utilization')) is not None and number(target['utilization'])>1+1e-9:
            status='NEVYHOVUJE'
        elif status.startswith('VYHOVUJE') and not target:
            status='NEPOSOUZENO'
        notes=_notes(reviewed['errors'],reviewed['warnings'],reviewed['audit_notes'],issues,
                     [raw.get('note'),meta.get('cover_resolution_note')],str(payload.get('note') or '').split(' • '))
        rows.append(dict(domain_id='thermal_breaks',domain='Izolační nosníky',group='Záměny',
            report_tab='substitution',report_kind='iso.substitution',name=str(raw.get('position','')),
            position=str(raw.get('position','')),quantity=raw.get('quantity'),
            source=str(raw.get('source_text') or snap.get('designation') or '—'),
            source_designation=str(raw.get('source_text') or snap.get('designation') or '—'),
            target_designation=str(target.get('designation') or '—'),source_meta=meta,
            source_actions=actions,target=target,candidate={'designation':target.get('designation'),
                'utilization':target.get('utilization')} if target else None,
            source_catalog=_catalog_source(snap), source_snapshot=deepcopy(snap),
            status=status,acceptance_text=reviewed['acceptance_text'],notes=notes,
            display=deepcopy(payload),calculation_valid=not issues))
    return rows


def iso_decoder_rows(owner):
    import project_model
    import substitution_workspace as sub
    import isokorb_families_304 as parser
    rows=[]
    for raw in getattr(getattr(owner,'project',None),'rows',[]):
        snap=_dict(raw.get('snapshot')); selection=_dict(raw.get('selection'))
        source=str(raw.get('source_text') or snap.get('designation') or '—')
        parsed=parser.parse(source)
        status='DEKÓDOVÁNO – NEPOSOUZENO'
        notes=_notes(raw.get('note'),snap.get('substitution_note'))
        db=getattr(owner,'database',None) or getattr(owner,'db',None)
        if db is not None:
            rs,_,message=project_model.row_status(db,raw)
            if rs!='ok':
                status='OVĚŘIT KATALOG'; notes.append(message)
        if snap.get('substitution_policy') in {'manual','none','disabled'}:
            status='ZVLÁŠTNÍ POSOUZENÍ'
        from decoder_length_320 import capacity_length_issue
        issue = capacity_length_issue(raw)
        if issue:
            status = 'OVĚŘIT DÉLKU'; notes.append(issue)
        meta=sub.source_metadata(raw)
        if parsed and parsed.family=='AP':
            meta['source_height_mm']=None
        rows.append(dict(domain_id='thermal_breaks',domain='Izolační nosníky',group='Dekodér',
            report_tab='decoder',report_kind='iso.decoder',name=str(raw.get('position','')),
            position=str(raw.get('position','')),quantity=raw.get('quantity'),source_designation=source,
            target_designation=str(snap.get('designation') or '—'),source_meta=deepcopy(meta),
            source_snapshot=deepcopy(snap),selection=deepcopy(selection),
            source_catalog=_catalog_source(snap),status=status,notes=notes,candidate=None,
            parsed_fields=deepcopy(parsed.fields) if parsed else {}))
    return rows


def shear_decoder_rows(owner):
    rows=[]
    for i,data in enumerate(getattr(owner,'shear_decoder_rows',[]),1):
        if not isinstance(data,dict):
            continue
        rows.append(dict(domain_id='shear_dowels',domain='Smykové trny',group='Dekodér',
            report_tab='decoder',report_kind='shear.decoder',name=str(data.get('name') or f'S{i:03d}'),
            position=str(data.get('name') or f'S{i:03d}'),quantity=data.get('quantity'),
            source_designation=str(data.get('designation') or '—'),target_designation='',
            decoder_data=deepcopy(data),status='DEKÓDOVÁNO – NEPOSOUZENO',notes=[],candidate=None))
    return rows


def collect_sections(owner):
    import pdf_scope
    import pdf_context_240
    return {('thermal_breaks','decoder'):iso_decoder_rows(owner),
            ('thermal_breaks','design'):deepcopy(pdf_scope._iso_design_rows(owner)),
            ('thermal_breaks','substitution'):iso_substitution_rows(owner),
            ('shear_dowels','decoder'):shear_decoder_rows(owner),
            ('shear_dowels','design'):deepcopy(pdf_scope._shear_design_rows(owner)),
            ('shear_dowels','substitution'):deepcopy(pdf_context_240._structured(owner))}


def context(rows):
    keys={(r.get('domain_id'),r.get('report_tab')) for r in rows}
    labels={('thermal_breaks','decoder'):('Dekodér izolačních nosníků','Identifikace katalogového prvku'),
            ('thermal_breaks','substitution'):('Záměny izolačních nosníků','Katalogové porovnání záměny'),
            ('thermal_breaks','design'):('Návrh nosníků HIT','Statická kontrola návrhu HIT'),
            ('shear_dowels','decoder'):('Dekodér smykových trnů','Identifikace smykového trnu'),
            ('shear_dowels','design'):('Návrh smykových trnů','Statická kontrola návrhu trnu'),
            ('shear_dowels','substitution'):('Záměny smykových trnů','Kontrola záměny smykového trnu')}
    return labels.get(next(iter(keys)), ('Technické prvky – přehled AKCE','Technický detail prvku')) if len(keys)==1 else ('Technické prvky – přehled AKCE','Technický detail prvku')


def _summary(row):
    kind=row.get('report_kind'); c=_dict(row.get('candidate'))
    if kind=='iso.substitution' and row.get('non_structural'):
        return row['source_designation'],row['target_designation'],'mezivýplň'
    if kind=='iso.substitution':
        return row['source_designation'],row['target_designation'],pct(_dict(row.get('target')).get('utilization'))
    if kind in {'iso.decoder','shear.decoder'}:
        return row['source_designation'],'Identifikace katalogového prvku','neposouzeno'
    if row.get('domain_id')=='shear_dowels' and row.get('report_tab')=='substitution':
        if row.get('verification_mode')=='ved':
            control='η '+pct(c.get('utilization'))
        else:
            control=pct(row.get('capacity_ratio'))+' VRd'
        return row.get('source_designation','—'),row.get('target_designation','—'),control
    import hit_pdf
    return hit_pdf._input_summary(row,with_actions=True),str(c.get('designation') or '—'),('a max '+fmt(c.get('spacing_max'),3)+' m' if number(c.get('spacing_max')) else pct(c.get('utilization')))


def install(base_app):
    import pdf_scope,hit_pdf
    import catalog_engine
    if getattr(hit_pdf,'_turto_pdf_data_304',False):
        return
    base=hit_pdf._base; cls=hit_pdf._ProposalReport
    old_card=cls.card_flows; old_logo=cls.logo_draw
    def color(status):
        text=str(status or '')
        return base.SUCCESS if text.startswith('VYHOVUJE') else base.DANGER if text.startswith(('NEVYHOVUJE','NELZE','CHYBA')) else base.WARNING
    def logo(self,c):
        try:
            from reportlab.lib.utils import ImageReader
            import branding_301
            image=ImageReader(io.BytesIO(branding_301.logo_bytes()))
            c.drawImage(image,self.margin,self.h-69,width=69,height=53,preserveAspectRatio=True,mask='auto')
        except Exception:
            LOG.exception('PDF: nelze načíst schválené logo, používá se původní logo')
            old_logo(self,c)
    def header(self,c,title,page,total):
        self.logo_draw(c); x=self.margin+82; w=self.width-82
        self.draw(c,self.p(title,size=15,bold=True,color=base.NAVY),15,x,w)
        self.draw(c,self.p('TURTO '+VERSION+' • '+self.generated,size=10,color=base.MUTED),36,x,w)
        self.draw(c,self.p(self.project,bold=True),53,x,w)
        c.setStrokeColor(self.b['colors'].HexColor(base.TEAL)); c.setLineWidth(1)
        c.line(self.margin,self.h-self.top+5,self.w-self.margin,self.h-self.top+5)
        fy=self.h-60; c.setStrokeColor(self.b['colors'].HexColor(base.BORDER)); c.setLineWidth(.5)
        c.line(self.margin,64,self.w-self.margin,64)
        self.draw(c,self.p(self.creator,size=9),fy,width=self.width-90)
        self.draw(c,self.p(f'{page} / {total}',align=2,size=10),fy,self.w-self.margin-80,80)
        self.draw(c,self.p('Katalogová pomůcka. Identifikace není statické posouzení; záměnu musí schválit statik stavby.',size=9,color=base.MUTED),fy+16)
    def summary_header(self):
        widths=[50.,153.,158.,76.,self.width-437.]
        labels=['Pozice / ks','Zdroj / zadání','Výsledek / náhrada','Kontrola','Stav']
        return self.table([[self.p(v,bold=True,size=10,color=base.WHITE) for v in labels]],widths,background=base.NAVY),widths
    def summary_row(self,row,index,widths):
        src,dst,control=_summary(row); status=str(row.get('status','NEPOSOUZENO'))
        category=str(row.get('domain',''))+' → '+str(row.get('group',''))
        return self.table([[self.p(str(row.get('name','—'))+'\n'+fmt(row.get('quantity'),0)+' ks',bold=True),
            self.p(category+'\n'+str(src),size=10.5),self.p(dst,bold=True,size=10.5),self.p(control,align=2,size=10.5),
            self.p(status,bold=True,size=10,color=color(status))]],widths,grid=True,background=base.WHITE if index%2==0 else base.PANEL)
    def summary_pages(self):
        head,widths=self.summary_header()
        states=[str(r.get('status','')) for r in self.rows]
        ok=sum(s.startswith('VYHOVUJE') for s in states)
        fail=sum(s.startswith(('NEVYHOVUJE','NELZE','CHYBA')) for s in states)
        intro=self.p(f'{len(self.rows)} pozic • vyhovuje {ok} • neposouzeno / k ověření {len(states)-ok-fail} • nevyhovuje / nelze {fail}',bold=True)
        flows=[intro,self.p('Rozsah a stav odpovídají jednotlivým částem AKCE. Katalogové hodnoty a skutečné návrhové účinky se nerozlišují pouze barvou.',size=10,color=base.MUTED),self.b['Spacer'](1,6),head]
        pages=[]; y=self.top+sum(self.height(f) for f in flows)
        for i,row in enumerate(self.rows):
            pending=[self.summary_row(row,i,widths)]
            while pending:
                f=pending.pop(0); h=self.height(f)
                if y+h<=self.h-self.bottom:
                    flows.append(f); y+=h; continue
                if len(flows)>1:
                    pages.append(('summary',flows)); flows=[head]; y=self.top+self.height(head)
                if self.height(f)>self.h-self.bottom-y:
                    f.splitInRow=1
                    parts=f.split(self.width,self.h-self.bottom-y)
                    if not parts:
                        raise hit_pdf.PdfExportError('Souhrnný řádek nelze rozdělit.')
                    flows.append(parts[0]); y+=self.height(parts[0]); pending=parts[1:]+pending
                    pages.append(('summary',flows)); flows=[head]; y=self.top+self.height(head)
                else:
                    pending.insert(0,f)
        if len(flows)>1: pages.append(('summary',flows))
        return pages
    def keytable(self,entries,width):
        return self.table([[self.p(k,bold=True,size=10.5),self.p(v,size=10.5)] for k,v in entries],[width*.30,width*.70],grid=True)
    def card(self,row,refs):
        kind=row.get('report_kind'); width=self.width-14
        if kind=='iso.substitution' and row.get('non_structural'):
            m=_dict(row.get('source_meta'))
            return [self.p('Původní: '+row['source_designation'],bold=True),
                    self.p('Náhrada: '+row['target_designation'],bold=True,color=base.TEAL),
                    keytable(self,[('Tloušťka izolantu',fmt(m.get('source_insulation_mm'),0)+' mm'),
                                   ('Výška',fmt(m.get('source_height_mm'),0)+' mm')],width),
                    self.p('Nenosný výplňový prvek – bez statického posouzení.'),
                    self.p(' '.join(row.get('notes',[])),size=10)]
        if kind=='iso.substitution':
            t=_dict(row.get('target')); m=_dict(row.get('source_meta')); display=_dict(row.get('display'))
            flows=[self.p('Původní: '+row['source_designation'],bold=True),
                   self.p('Náhrada HIT: '+row['target_designation'],bold=True,color=base.TEAL)]
            entries=[('Izolant zdroj → HIT',fmt(m.get('source_insulation_mm'),0)+' → '+fmt(t.get('target_insulation_mm'),0)+' mm'),
                ('Výška zdroj → HIT',fmt(m.get('source_height_mm'),0)+' → '+fmt(t.get('height_mm'),0)+' mm'),
                ('Krytí zdroj → HIT',str(display.get('source_cover') or fmt(m.get('source_cover_mm'),0))+' → '+str(display.get('target_cover') or fmt(t.get('cover_mm'),0))),
                ('Délka zdroj → HIT',fmt(m.get('source_length_mm'),0)+' → '+fmt(t.get('length_mm'),0)+' mm'),
                ('Beton',str(m.get('source_concrete') or '—')+' → '+str(t.get('concrete') or '—')),
                ('Tlakový přenos',str(m.get('source_compression_text') or '—')+' → '+str(t.get('compression_text') or '—'))]
            if m.get('geometry_display'): entries.append(('Geometrie',m['geometry_display']))
            flows+=[keytable(self,entries,width),self.b['Spacer'](1,4),
                    self.p('Katalogové porovnání 1 : 1 – požadavek je únosnost původního prvku, nikoliv zadané zatížení stavby.',size=10.5,color=base.MUTED),
                    base._Report.checks_table(self,row,width)]
            flows.append(self.p('Celkové využití záměny: '+pct(t.get('utilization'))+' • '+str(row['status']),bold=True,color=color(row['status'])))
            if row.get('acceptance_text'): flows.append(self.p(row['acceptance_text'],bold=True))
            if t.get('mode'): flows.append(self.p('Rozhodující kontrola: '+str(t['mode']),size=10.5))
            if row.get('source_catalog'): flows.append(self.p('Zdroj původního prvku: '+row['source_catalog'],size=10,color=base.MUTED))
            if t.get('page'): flows.append(self.p('Zdroj HIT: '+str(t['page']),size=10,color=base.MUTED))
            if refs: flows.append(self.p('Poznámky a omezení: '+', '.join(f'[{n}]' for n in refs)+' (příloha).',size=10,color=base.MUTED))
            return flows
        if kind=='iso.decoder':
            snap=_dict(row.get('source_snapshot')); m=_dict(row.get('source_meta')); f=_dict(row.get('parsed_fields'))
            flows=[self.p('Původní označení: '+row['source_designation'],bold=True),self.p('Rozpoznaný typ: '+row['target_designation'],bold=True,color=base.TEAL)]
            selection=_dict(row.get('selection'))
            entries=[('Řada / generace',str(selection.get('model','—'))+' / '+str(selection.get('generation','—'))),
                ('Izolant',fmt(snap.get('insulation_thickness_mm'),0)+' mm'),('Beton katalogu',str(selection.get('concrete_min','—'))),
                ('Výška prvku',fmt(m.get('source_height_mm'),0)+' mm'),('Délka prvku',fmt(m.get('source_length_mm') or snap.get('element_length_mm'),0)+' mm')]
            if f.get('anchorage'): entries+=[('Délka zabudování LR',f['anchorage']+' mm'),('Šířka B',f['width']+' mm')]
            else: entries.append(('Krytí / varianta',str(selection.get('cover','—'))))
            flows.append(keytable(self,entries,width))
            flows.append(self.p('Katalogové údaje – bez statického posouzení',bold=True))
            for result in snap.get('results',[]):
                flows.append(self.p(catalog_engine.format_result(result),size=11))
            if not snap.get('results'): flows.append(self.p('Katalogové hodnoty nejsou k dispozici.',color=base.WARNING))
            if row.get('source_catalog'): flows.append(self.p('Zdroj: '+row['source_catalog'],size=10,color=base.MUTED))
            if refs: flows.append(self.p('Poznámky: '+', '.join(f'[{n}]' for n in refs)+' (příloha).',size=10))
            return flows
        if kind=='shear.decoder':
            d=_dict(row.get('decoder_data'))
            entries=[('Výrobce / rodina',str(d.get('manufacturer','—'))+' / '+str(d.get('family','—'))),
                     ('Tloušťka desky h',fmt(d.get('slab_mm'),0)+' mm'),('Spára',fmt(d.get('gap_mm'),0)+' mm'),
                     ('Beton',str(d.get('concrete') or '—')),('Pohyb',str(d.get('movement') or '—'))]
            for k,label in [('vrd','VRd [kN/prvek]'),('archive_vrd','Archivní VRd [kN/prvek]'),('reference_vrd','Referenční VRd [kN/prvek]'),('capacity_text','Katalogová hodnota'),('archive_source','Archivní zdroj'),('archive_note','Archivní poznámka'),('source','Zdroj'),('note','Poznámka')]:
                if d.get(k) not in (None,''): entries.append((label,str(d[k])))
            return [self.p(row['source_designation'],bold=True),keytable(self,entries,width),
                    self.p('Identifikace prvku a katalogové údaje nejsou statickým posouzením.',color=base.WARNING)]
        return old_card(self,row,refs)
    def card_title(self,card):
        row=card.row; text=str(row.get('group',''))+' • '+str(row.get('name','—'))+' • '+fmt(row.get('quantity'),0)+' ks'
        if card.continued: text+=' • pokračování'
        width=self.width-14
        return self.table([[self.p(text,bold=True),self.p(row.get('status','NEPOSOUZENO'),align=2,bold=True,size=10,color=color(row.get('status')))]],[width-165,165],background=base.PANEL,padding=2)
    def write(self,path):
        title,detail=context(self.rows)
        plan=self.summary_pages()+self.detail_pages()+self.notes_pages()
        c=self.b['Canvas'](str(path),pagesize=self.b['A4'],pageCompression=1)
        c.setTitle('TURTO – '+title+' – '+self.project); c.setAuthor(self.creator); c.setCreator('TURTO '+VERSION); c.setSubject(title)
        counts={'summary':0,'detail':0,'notes':0}
        for index,(kind,items) in enumerate(plan,1):
            self.header(c,{'summary':title,'detail':detail,'notes':'Poznámky a omezení'}[kind],index,len(plan)); y=self.top
            c.bookmarkPage(f'page{index}'); counts[kind]+=1
            c.addOutlineEntry({'summary':'Souhrn','detail':'Detaily','notes':'Poznámky'}[kind]+' '+str(counts[kind]),f'page{index}',0)
            if kind=='detail':
                for item in items: y=self.card_draw(c,item,y)+6
            else:
                for flow in items: y=self.draw(c,flow,y)
            if y>self.h-self.bottom+6.2: raise hit_pdf.PdfExportError('Obsah PDF přesahuje tiskovou oblast.')
            c.showPage()
        c.save()
        return dict(pages=len(plan),**{k+'_pages':v for k,v in counts.items()})
    pdf_scope.collect_report_sections=collect_sections
    cls.header=header; cls.logo_draw=logo; cls.summary_header=summary_header; cls.summary_row=summary_row
    cls.summary_pages=summary_pages; cls.card_flows=card; cls.card_title=card_title; cls.write=write
    hit_pdf._turto_pdf_data_304=True


def selftest():
    assert number(None) is None and number('nan') is None and number(0)==0
    assert context([{'domain_id':'thermal_breaks','report_tab':'substitution'}])[0]=='Záměny izolačních nosníků'
    assert not _selected({'selected_target_id':'missing','targets':[{'id':'other'}]})
