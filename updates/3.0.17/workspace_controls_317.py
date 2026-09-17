"""Consistent table actions and responsive toolbars across workspaces."""
from functools import wraps
import tkinter as tk
from tkinter import ttk


def walk(widget):
    yield widget
    for child in widget.winfo_children():
        yield from walk(child)


def visible(widget):
    """Canvas children can report mapped while an ancestor tab is hidden."""
    if not widget.winfo_ismapped():
        return False
    current = widget
    while current.master is not None:
        parent = current.master
        if isinstance(parent, ttk.Notebook) and str(current) != parent.select():
            return False
        if not parent.winfo_ismapped():
            return False
        current = parent
    return True


class FlowToolbar:
    def __init__(self, frame, children):
        self.frame = frame
        self.items = list(children)
        self.pending = None
        self.last_width = None
        self.layout = None
        columns, _ = frame.grid_size()
        for column in range(columns):
            frame.columnconfigure(column, weight=0, minsize=0)
        for child in children:
            if child.winfo_manager() == 'pack':
                child.pack_forget()
            else:
                child.grid_forget()
        frame.grid_propagate(False)
        frame.pack_propagate(False)
        frame.bind('<Configure>', self.schedule, add='+')
        frame.bind('<Map>', self.schedule, add='+')
        frame.bind('<Destroy>', self.close, add='+')
        for child in children:
            if isinstance(child,ttk.Label):
                child.bind('<Configure>',self.content_changed,add='+')
        self.schedule()

    def content_changed(self, event=None):
        self.last_width=None
        self.schedule()

    def close(self, event):
        if event.widget is self.frame and self.pending:
            self.frame.after_cancel(self.pending)
            self.pending = None

    def schedule(self, event=None):
        if self.pending is None:
            self.pending = self.frame.after_idle(self.arrange)

    def arrange(self):
        self.pending = None
        width = self.frame.winfo_width()
        if width < 100 or width == self.last_width:
            return
        self.last_width = width
        x = y = row_height = 0
        positions = []
        for child in self.items:
            if isinstance(child, ttk.Frame):
                if x: y += row_height+4
                positions.append((child,0,y,max(1,width-7)))
                y += child.winfo_reqheight()+4; x = row_height = 0
                continue
            if isinstance(child, ttk.Label) and child.cget('text'):
                child.configure(wraplength=max(140,min(500,width-12)))
            required = child.winfo_reqwidth()+7
            if x and x+required > width-6:
                y += row_height+4; x = row_height = 0
            positions.append((child,x,y,None))
            row_height = max(row_height,child.winfo_reqheight())
            x += required
        layout = (tuple((str(c),x,y,w) for c,x,y,w in positions),y+row_height+5)
        if layout == self.layout:
            return
        self.layout = layout
        self.frame.configure(height=y+row_height+5)
        for child,x,y,width in positions:
            if width is None: child.place(x=x,y=y)
            else: child.place(x=x,y=y,width=width)



def apply(owner):
    if getattr(owner, '_controls_applied_317', False):
        return
    owner._controls_applied_317 = True
    widgets = list(walk(owner))
    # The same entry already searches all manufacturers. This second selector
    # offered only Leviat products and looked like a catalogue filter.
    choice = getattr(owner, 'hsd_catalog_choice', None)
    if choice is not None:
        choice.grid_remove()
    for w in widgets:
        if isinstance(w, ttk.Label):
            text = str(w.cget('text'))
            if text == 'Izolační nosníky' and isinstance(w.master,ttk.Frame) and all(isinstance(c,ttk.Label) for c in w.master.winfo_children()):
                w.master.grid_remove()
            elif text == 'Další ověřené moduly Leviat HIT:':
                w.configure(text='Návrhové moduly HIT:')
            elif text == 'Původní ověřené moduly; bez změny statického výpočtu.':
                w.pack_forget()
        elif isinstance(w, ttk.Menubutton) and str(w.cget('text')) == 'Další…':
            w.configure(text='Řádky…', width=9)
        elif isinstance(w, ttk.Button) and str(w.cget('text')) in ('Hromadné dekódování z výkazu','Načíst výkaz ze souboru / textu…'):
            w.configure(text='Načíst výkaz…')
    # Wrap existing actions without rebuilding their commands, forms or tables.
    owner._flow_toolbars_317 = []
    for frame in widgets:
        if not isinstance(frame, ttk.Frame): continue
        children = [w for w in frame.winfo_children() if w.winfo_manager() in ('grid','pack')]
        buttons = [w for w in children if isinstance(w,(ttk.Button,ttk.Menubutton))]
        if len(buttons)<3 or any(not isinstance(w,(ttk.Button,ttk.Menubutton,ttk.Label,ttk.Frame,ttk.Separator)) for w in children):
            continue
        if any(isinstance(w,ttk.Frame) and not all(isinstance(c,(ttk.Button,ttk.Label,ttk.Separator)) for c in w.winfo_children()) for w in children):
            continue
        if any(w.winfo_manager()=='grid' for w in children):
            children.sort(key=lambda w:(int(w.grid_info().get('row',0)),int(w.grid_info().get('column',0))))
        owner._flow_toolbars_317.append(FlowToolbar(frame,children))
    # Actions on selected rows are unavailable until a row is selected.
    labels = {'Upravit pozici / ks','Duplikovat','Nahoru','Dolů','Smazat','Detail prvku',
              'Doplnit h / spáru / beton…','Převést do Záměn','Navrhnout vybrané',
              'Upřesnit zdroj / geometrii…','Vybrat variantu…','✓ Potvrdit geometrii',
              'Detail záměny','✓ Potvrdit záměnu…','Zrušit potvrzení',
              'Ověřit vybrané dle VEd…','Vybrané zpět na katalogovou VRd'}
    owner._selection_actions_317=[]
    notebooks=[getattr(owner,'main_notebook',None),getattr(owner,'shear_notebook',None)]
    for notebook in notebooks:
        if notebook is None:continue
        for tab in notebook.tabs():
            panel=owner.nametowidget(tab)
            trees=[w for w in walk(panel) if isinstance(w,ttk.Treeview) and 'Suggest' not in str(w.cget('style'))]
            if not trees:continue
            # Prefer the principal data table; alternatives have a browse selection.
            tree=max(trees,key=lambda w:len(w.cget('columns')))
            buttons=[w for w in walk(panel) if isinstance(w,ttk.Button) and str(w.cget('text')) in labels]
            if not buttons:continue
            def sync(event=None, tree=tree, buttons=buttons):
                selected=bool(tree.selection())
                for button in buttons:
                    previous=getattr(button,'_empty_selection_317',None)
                    if not selected:
                        if previous is None:button._empty_selection_317=button.instate(['disabled'])
                        button.state(['disabled'])
                    elif previous is not None:
                        if not previous:button.state(['!disabled'])
                        del button._empty_selection_317
            tree.bind('<<TreeviewSelect>>',sync,add='+')
            tree.bind('<Map>',sync,add='+')
            owner._selection_actions_317.append((tree,buttons,sync));sync()
    # Highlight active filters using variable traces, without polling/redrawing rows.
    style=ttk.Style(owner)
    style.configure('ActiveFilter.TEntry',fieldbackground='#fff3cd',foreground='#4d3c00')
    for name,var in vars(owner).copy().items():
        if 'filter' not in name or not isinstance(var,tk.StringVar):continue
        for w in widgets:
            if isinstance(w,ttk.Entry) and str(w.cget('textvariable'))==str(var):
                original=str(w.cget('style')) or 'TEntry'
                def update(*_,w=w,var=var,original=original):
                    if w.winfo_exists():w.configure(style='ActiveFilter.TEntry' if var.get().strip() else original)
                var.trace_add('write',update);update()


def install(base):
    cls=base.ThermalConnectorApp
    if getattr(cls,'_controls_installed_317',False):return
    original=cls._build_body
    @wraps(original)
    def body(owner):
        original(owner)
        apply(owner)
    cls._build_body=body
    cls._controls_installed_317=True
