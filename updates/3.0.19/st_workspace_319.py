"""Expose ST and WT in the existing persisted wall/beam design workspace."""
from functools import wraps
from tkinter import ttk


def install(base):
    import design_groups_restore as groups
    groups.GROUPS=tuple((key,'Nosníky ST / stěny WT','HIT-ST · HIT-WT') if key=='wt' else (key,label,detail)
                       for key,label,detail in groups.GROUPS)
    groups._CATALOG_LABEL['wt']='Leviat HIT – Nosníky ST / stěny WT'
    cls=base.ThermalConnectorApp
    original=cls._build_hit_tab
    @wraps(original)
    def build(self,*a,**k):
        result=original(self,*a,**k)
        self.hit_design_notebook.tab(self.hit_wt_tab,text='Nosníky ST / stěny WT')
        pending=[self.hit_wt_tab]
        while pending:
            w=pending.pop();pending.extend(w.winfo_children())
            if isinstance(w,ttk.Button) and w.cget('text') == '+ Přidat řádek':
                w.configure(text='+ Přidat WT')
        return result
    cls._build_hit_tab=build
    original_init=cls.__init__
    @wraps(original_init)
    def init(self,*a,**k):
        original_init(self,*a,**k)
        pending=[self.hit_tab]
        while pending:
            w=pending.pop();pending.extend(w.winfo_children())
            if isinstance(w,ttk.Label):
                text=str(w.cget('text'))
                if 'PDF zahrnuje' in text or 'Export PDF nahoře' in text:
                    w.configure(text=text.replace('Stěny WT','Nosníky ST / stěny WT').replace('i WT.','i ST / WT.'))
    cls.__init__=init
