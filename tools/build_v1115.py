from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
VERSION = "1.1.15"
BASE = ROOT / "updates/1.1.14"
OUT = ROOT / "updates" / VERSION
REPO = "jaroslavkucacz-code/TURTO-Izolacni-nosniky"

NOTES = '''TURTO ISO v1.1.15
- V kartě Záměny za HIT je nové tlačítko „✓ Potvrdit záměnu…“. Je oddělené od potvrzení geometrie OU/OD.
- Před potvrzením se označená pozice přepočítá aktuálním návrhářem. Dialog zobrazí původní odhad a konkrétní vyhovující HIT, který uživatel přijímá.
- Potvrzení ruší pouze upozornění na nahrazení nevyhovujícího prvotního odhadu vyhovující variantou. Neodstraní chybu, nevyhovující výpočet ani nevyřešenou geometrii či jiné technické upozornění.
- Stav v tabulce, Excelu a PDF se po platném potvrzení změní na VYHOVUJE. Původní upozornění zůstává v projektu a v příloze PDF jako potvrzená informace, nikoli nevyřešená kontrola.
- Potvrzení se ukládá do projektu .tinp s časem a vazbou na přesné vstupy, zvolený HIT a výsledek výpočtu. Změna vstupů nebo varianty je zneplatní; identický přepočet je zachová. Potvrzení lze také výslovně zrušit.
- Ručně vybraný HIT se při přepočtu zachová, pokud je nadále mezi vyhovujícími kandidáty.
- Text v patičce PDF nově zní „Nutno schválit statikem stavby.“ Uživatelské potvrzení není schválením statikem.
- Zůstává A4 na výšku, vektorové firemní logo, vektorový text, 11pt hodnoty a kompaktní rozložení. Výpočtové jádro a katalogová data se nemění.
'''


def change(text: str, old: str, new: str, count: int = 1) -> str:
    if text.count(old) != count:
        raise RuntimeError(f"Patch needs {count} matches, got {text.count(old)}: {old[:100]}")
    return text.replace(old, new)


METHODS = '''    def confirm_substitution_choice(self) -> None:
        selected = list(self.sub_tree.selection()) if hasattr(self, "sub_tree") else []
        if len(selected) != 1:
            messagebox.showinfo("Potvrdit záměnu", "Vyberte právě jednu pozici, jejíž navržený HIT chcete potvrdit.", parent=self)
            return
        if self._settings() is None:
            return
        # Nikdy nepřijmout starý snímek výsledku bez nového ověření jádrem.
        try:
            self.design_substitutions(True)
        except Exception as exc:
            messagebox.showerror("Potvrzení záměny", "Nový přepočet se nezdařil. Záměna nebyla potvrzena.\\n\\n" + str(exc), parent=self)
            return
        row = self.project.row_by_id(selected[0])
        if row is None:
            return
        meta = source_metadata(row)
        _actions, warnings = source_element_actions(row)
        state = review_state(row, meta, warnings)
        if not state["can_accept"]:
            messagebox.showwarning(
                "Záměnu nelze potvrdit",
                "Nejprve vyřešte zbývající podmínky:\\n\\n" + "\\n".join(state["blockers"])
                + "\\n\\nPotvrzení záměny nenahrazuje potvrzení geometrie ani statický výpočet.",
                parent=self,
            )
            return
        if state["accepted"]:
            messagebox.showinfo("Potvrdit záměnu", "Tato varianta a aktuální výpočet už jsou potvrzené.", parent=self)
            return
        mapping = row["mapping"]
        target = exact_target(mapping)
        estimate = str(mapping.get("estimated_type") or "—")
        prompt = (
            f"Pozice {row.get('position', '')}\\n"
            f"Původní odhad: {estimate}\\n\\n"
            f"Potvrzovaný HIT:\\n{target.get('designation', '')}\\n"
            f"Využití: {fmt(float(target['utilization']) * 100.0)} %\\n\\n"
            + ("\\n".join(state["warnings"]) + "\\n\\n" if state["warnings"] else "")
            + "Potvrdit použití právě tohoto vyhovujícího HIT?\\n"
            "Tím se přijímá navržená varianta, nikoli nevyhovující původní odhad.\\n\\n"
            "Nutno schválit statikem stavby."
        )
        if not messagebox.askyesno("Potvrdit navrženou záměnu", prompt, parent=self):
            return
        try:
            accept_substitution(row, meta, warnings)
        except ValueError as exc:
            messagebox.showwarning("Záměnu nelze potvrdit", str(exc), parent=self)
            return
        self.project.touch()
        if hasattr(self, "mark_project_dirty"):
            self.mark_project_dirty()
        self.refresh_substitution_tree()
        if hasattr(self, "refresh_project_tree"):
            self.refresh_project_tree(select_ids=selected)
        self.sub_status_var.set(f"Záměna pozice {row.get('position', '')} potvrzena uživatelem. Uložte projekt (Ctrl+S).")

    def revoke_substitution_choice(self) -> None:
        selected = list(self.sub_tree.selection()) if hasattr(self, "sub_tree") else []
        if len(selected) != 1:
            messagebox.showinfo("Zrušit potvrzení", "Vyberte právě jednu pozici.", parent=self)
            return
        row = self.project.row_by_id(selected[0])
        if row is None or not row.get("mapping", {}).get("substitution_acceptance"):
            messagebox.showinfo("Zrušit potvrzení", "Pozice nemá uložené potvrzení záměny.", parent=self)
            return
        if not messagebox.askyesno("Zrušit potvrzení záměny", f"Zrušit uživatelské potvrzení pozice {row.get('position', '')}? Geometrie a navržený HIT zůstanou beze změny.", parent=self):
            return
        _actions, warnings = source_element_actions(row)
        revoke_acceptance(row, source_metadata(row), warnings)
        self.project.touch()
        if hasattr(self, "mark_project_dirty"):
            self.mark_project_dirty()
        self.refresh_substitution_tree()
        if hasattr(self, "refresh_project_tree"):
            self.refresh_project_tree(select_ids=selected)
        self.sub_status_var.set("Potvrzení záměny zrušeno; původní upozornění je znovu aktivní.")

'''


def patch_workspace(text: str) -> str:
    text = change(text, 'SUBSTITUTION_MODULE_VERSION = "1.1.14"', 'SUBSTITUTION_MODULE_VERSION = "1.1.15"')
    text = change(text, 'from hit_core import Candidate, DirectionalActions, HitDatabase, fmt',
        'from hit_core import Candidate, DirectionalActions, HitDatabase, fmt\nfrom substitution_review import accept_substitution, exact_target, review_state, revoke_acceptance')
    text = change(text, '        ("status", "Stav", 112, "center", False),',
        '        ("status", "Stav", 112, "center", False),\n        ("confirmation", "Potvrzení záměny", 220, "w", False),')
    anchor = '        bar.columnconfigure(20, weight=1)'
    text = change(text, anchor, '''        review_bar = ttk.Frame(bar, style="App.TFrame")
        review_bar.grid(row=1, column=0, columnspan=21, sticky="ew", pady=(7, 0))
        ttk.Button(review_bar, text="✓ Potvrdit záměnu…", style="Accent.TButton", command=self.confirm_substitution_choice).pack(side="left")
        ttk.Button(review_bar, text="Zrušit potvrzení", command=self.revoke_substitution_choice).pack(side="left", padx=(7, 0))
        ttk.Label(review_bar, text="Přijetí vyhovujícího HIT místo původního odhadu; geometrie OU/OD se potvrzuje samostatně.", style="Muted.TLabel").pack(side="left", padx=(12, 0))
''' + anchor)
    old = '''        status = str(mapping.get("status", "not_run"))
        if status == "ok" and meta.get("geometry_target") and not meta.get("geometry_confirmed"):
            status = "review"
'''
    text = change(text, old, '''        reviewed = review_state(row, live_meta, action_warnings)
        status = reviewed["status"]
''')
    old = '''        warnings = list(action_warnings)
        warnings.extend(str(value) for value in meta.get("warnings", []) if str(value))
        warnings.extend(str(value) for value in mapping.get("warnings", []) if str(value))
        errors = [str(value) for value in mapping.get("errors", []) if str(value)]
        if status == "error" and mapping.get("selected_target_id"):
            errors.append(str(mapping.get("selected_target_id")))
        notes = list(dict.fromkeys([*errors, *warnings]))
'''
    text = change(text, old, '''        warnings = reviewed["warnings"]
        errors = reviewed["errors"]
        notes = list(dict.fromkeys([*errors, *warnings, *reviewed["audit_notes"]]))
''')
    text = change(text, '            "status": status_text, "note": " • ".join(dict.fromkeys(notes)),',
        '            "status": status_text, "confirmation": reviewed["acceptance_text"], "note": " • ".join(dict.fromkeys(notes)),')
    # Both variant-selection paths invalidate acceptance only when a different candidate is used.
    old = '        mapping["selected_target_id"] = str(target.get("id"))\n        row["mapping"] = mapping'
    text = change(text, old, '''        if str(mapping.get("selected_target_id")) != str(target.get("id")):
            mapping.pop("substitution_acceptance", None)
        mapping["selected_target_id"] = str(target.get("id"))
        row["mapping"] = mapping
        _actions, _warnings = source_element_actions(row)
        mapping["status"] = review_state(row, source_metadata(row), _warnings)["status"]''', 2)
    text = change(text, '    def design_substitutions(self, selected_only: bool) -> None:', METHODS + '    def design_substitutions(self, selected_only: bool) -> None:')
    old = '''            row["mapping"] = {
                "status": "review" if warnings else "ok",
                "targets": targets,
                "selected_target_id": str(targets[0]["id"]),'''
    new = '''            chosen_id = str(previous_mapping.get("selected_target_id") or "")
            if not any(str(t.get("id")) == chosen_id for t in targets):
                chosen_id = str(targets[0]["id"])
            row["mapping"] = {
                "status": "review" if warnings else "ok",
                "targets": targets,
                "selected_target_id": chosen_id,'''
    text = change(text, old, new)
    old = '''            if warnings:
                review += 1
            else:
                ok += 1
        self.project.touch()'''
    new = '''            acceptance = previous_mapping.get("substitution_acceptance")
            if isinstance(acceptance, dict) and acceptance:
                row["mapping"]["substitution_acceptance"] = dict(acceptance)
                if not review_state(row, meta, action_warnings)["accepted"]:
                    row["mapping"].pop("substitution_acceptance", None)
            reviewed = review_state(row, meta, action_warnings)
            row["mapping"]["status"] = reviewed["status"]
            if reviewed["status"] == "error":
                failed += 1
            elif reviewed["status"] == "review":
                review += 1
            else:
                ok += 1
        self.project.touch()'''
    text = change(text, old, new)
    old = '''            notes: list[str] = []
            notes.extend(str(value) for value in mapping.get("errors", []) if str(value))
            notes.extend(str(value) for value in mapping.get("warnings", []) if str(value))
            notes.extend(str(value) for value in meta.get("warnings", []) if str(value))
            notes.extend(str(value) for value in action_warnings if str(value))'''
    new = '''            reviewed = review_state(row, live_meta, action_warnings)
            notes = [*reviewed["errors"], *reviewed["warnings"], *reviewed["audit_notes"]]'''
    text = change(text, old, new)
    text = change(text, '                "status": str(payload.get("status", "NEPOSOUZENO")),',
        '                "status": str(payload.get("status", "NEPOSOUZENO")),\n                "acceptance_text": reviewed["acceptance_text"],')
    return text


def patch_model(text: str) -> str:
    marker = '        "source_overrides":dict(raw_mapping.get("source_overrides",{})) if isinstance(raw_mapping.get("source_overrides",{}),dict) else {},'
    return change(text, marker, marker + '\n        "substitution_acceptance":copy.deepcopy(raw_mapping.get("substitution_acceptance",{})) if isinstance(raw_mapping.get("substitution_acceptance",{}),dict) else {},')


def patch_pdf(text: str) -> str:
    text = change(text, 'REPORT_VERSION = "1.1.14"', 'REPORT_VERSION = "1.1.15"')
    text = change(text, 'Požární odolnost se neposuzuje. Ověřit projektantem.', 'Nutno schválit statikem stavby.')
    marker = '        if t and lsrc != ldst and t.get("length_relation"):'
    return change(text, marker, '''        if row.get("acceptance_text"):
            flows.append(self.p(_text(row["acceptance_text"]), color=SUCCESS))
''' + marker)


def build() -> None:
    manifest_path = ROOT / "update_manifest.json"
    previous = json.loads(manifest_path.read_text(encoding="utf-8"))
    if previous.get("version") not in {"1.1.14", VERSION}:
        raise RuntimeError("Different release found; refusing to overwrite update manifest")
    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(BASE, OUT, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    for name, patch in (("substitution_workspace.py", patch_workspace), ("project_model.py", patch_model), ("substitution_pdf.py", patch_pdf)):
        path = OUT / name
        path.write_text(patch(path.read_text(encoding="utf-8")), encoding="utf-8")
    shutil.copyfile(ROOT / "tools/v1115_substitution_review.py", OUT / "substitution_review.py")
    app = OUT / "app.pyw"
    app.write_text(change(app.read_text(encoding="utf-8"), 'APP_VERSION = "1.1.14"', 'APP_VERSION = "1.1.15"'), encoding="utf-8")
    (OUT / "version.txt").write_text(VERSION + "\n", encoding="utf-8")
    (OUT / "RELEASE_NOTES.txt").write_text(NOTES, encoding="utf-8")
    for path in OUT.rglob("*"):
        if path.suffix in {".py", ".pyw"}:
            compile(path.read_text(encoding="utf-8-sig"), str(path), "exec")
    changed = {"app.pyw", "substitution_workspace.py", "project_model.py", "substitution_pdf.py", "version.txt", "RELEASE_NOTES.txt", "PDF_VERIFICATION.json"}
    unchanged = 0
    for path in BASE.rglob("*"):
        if path.is_file() and path.suffix != ".pyc" and "__pycache__" not in path.parts and path.relative_to(BASE).as_posix() not in changed:
            assert path.read_bytes() == (OUT / path.relative_to(BASE)).read_bytes(), str(path)
            unchanged += 1
    # Real UI tests need an X server on Linux; CI invokes this script under xvfb-run.
    spec = importlib.util.spec_from_file_location("verify_review", ROOT / "tools/verify_v1115.py")
    mod = importlib.util.module_from_spec(spec); sys.modules[spec.name] = mod; spec.loader.exec_module(mod)
    result = mod.verify(OUT, ROOT / "_diag_v1115")
    result.update(version=VERSION, unchanged_support_files=unchanged, structural_core_unchanged=True)
    data = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    (OUT / "REVIEW_VERIFICATION.json").write_text(data, encoding="utf-8")
    (ROOT / "_diag_v1115/verification.json").write_text(data, encoding="utf-8")
    (OUT / "PDF_VERIFICATION.json").write_text(json.dumps(result["pdf"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    paths = {str(item["path"]) for item in previous["files"]}
    paths.update({"substitution_review.py", "REVIEW_VERIFICATION.json"})
    files = []
    for rel in sorted(paths):
        path = OUT / rel
        if not path.is_file():
            raise RuntimeError("Missing update file: " + rel)
        files.append(dict(path=rel, url=f"https://raw.githubusercontent.com/{REPO}/main/updates/{VERSION}/{rel}", sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    previous.update(version=VERSION, files=files, notes="TURTO ISO: potvrzení konkrétní vyhovující záměny místo prvotního odhadu, uložené potvrzení v projektu, tabulce i PDF; patička Nutno schválit statikem stavby.")
    manifest_path.write_text(json.dumps(previous, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"PASS: release {VERSION}, {len(files)} updater files, {unchanged} support/data files unchanged")


if __name__ == "__main__":
    build()
