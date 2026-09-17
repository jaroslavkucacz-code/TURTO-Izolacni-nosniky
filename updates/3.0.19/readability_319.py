"""Legible point-sized Calibri, stronger contrast, and stable row heights.

Do not change Windows' global ClearType settings or Tk scaling. Text uses the
system DPI. Map handlers adjust only a newly mapped widget's explicit font;
they never rebuild rows or trigger a recurring refresh timer.
"""
from functools import wraps
import tkinter as tk
from tkinter import font as tkfont, ttk


def _styles(owner):
    style=owner.style
    for name in ('TEntry','TCombobox','TSpinbox','Shared.TEntry','Shared.TCombobox'):
        style.configure(name,font=('Calibri',11))
    for name in ('TLabel','Card.TLabel','CardAlt.TLabel','Muted.TLabel',
                 'MutedCard.TLabel','SmallCard.TLabel','Shared.TLabel','Warning.TLabel'):
        style.configure(name,font=('Calibri',10))
    height=max(29,tkfont.Font(owner,font=('Calibri',11)).metrics('linespace')+8)
    for name in ('Treeview','Data.Treeview','Project.Treeview','HSD.Data.Treeview'):
        style.configure(name,font=('Calibri',11),rowheight=height)
        style.configure(name+'.Heading',font=('Calibri',10,'bold'))
    owner.option_add('*TCombobox*Listbox.font',('Calibri',11))


def _mapped(event):
    widget=event.widget
    if getattr(widget,'_turto_font_checked_319',False):
        return
    widget._turto_font_checked_319=True
    try:
        if 'font' not in widget.keys() or not widget.cget('font'):
            return
        spec=tkfont.Font(root=widget,font=widget.cget('font')).actual()
        if spec['family'].lower() != 'calibri':
            return
        minimum=11 if isinstance(widget,(ttk.Entry,ttk.Combobox,ttk.Spinbox,tk.Entry,tk.Text)) else 10
        if 0 < spec['size'] < minimum:
            widget.configure(font=('Calibri',minimum,spec['weight'],spec['slant']))
    except tk.TclError:
        pass


def install(base):
    cls=base.ThermalConnectorApp
    if getattr(cls,'_turto_readability_319',False):return
    base.LIGHT.update(text='#101820',muted='#465362',border='#BBC6D1')
    base.DARK.update(text='#F4F7FA',muted='#C2CBD5')
    original_theme=cls._configure_theme
    @wraps(original_theme)
    def theme(self,*a,**k):
        result=original_theme(self,*a,**k)
        _styles(self)
        return result
    cls._configure_theme=theme
    original_init=cls.__init__
    @wraps(original_init)
    def init(self,*a,**k):
        original_init(self,*a,**k)
        _styles(self)  # Some legacy panels declare styles during construction.
        self.bind_all('<Map>',_mapped,add='+')
        pending=[self]
        while pending:
            w=pending.pop();pending.extend(w.winfo_children())
            event=type('FontEvent',(),{'widget':w})()
            _mapped(event)
    cls.__init__=init
    cls._turto_readability_319=True
