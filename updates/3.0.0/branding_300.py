from __future__ import annotations

"""TURTO 3.0.0 branding: selected thermal-break / shear-dowel symbol.

The logo bytes are embedded deliberately so the online update does not depend on
an external asset file. No catalogue, statical or project data are changed here.
"""

import tkinter as tk
from tkinter import ttk

VERSION = "3.0.0"

_LOGO_PNG_B64 = """
iVBORw0KGgoAAAANSUhEUgAAAJcAAABwCAYAAAAT3uJDAAAAAXNSR0IArs4c6QAAAARnQU1BAACxjwv8YQUAAAAJcEhZcwAAEnQAABJ0Ad5mH3gAAGBbSURB
VHhelb15vC3HVR76raru3nufcyfpSrKFZcnGkuVRRh7C4BmDsbFlgwnYYBMMcQL8HiRACCQkBEECmDAGgkOAkIQpyQuBAGbII7EJeMSTJCPJtoyxhTVe6ere
e4a9u7uq1vvjW6u695HMy+v72/fs3V1dtWrVmmqtVVWyeNY3KuxSCAD+FACq9l28hPAB/6tlH/mS7fesdgBQ8XYCBAIFINBam0wv2g2vgf/VknPIRfjb4FNV
QPh3epflajGre6rL4KztH+0noRQDSFUhEuyZlxDovHJVg5/t8rZM7VsxGIbYtLAm/27wCFDbUzieJtj4J0C11DoAtXH05/OWrS8z7IvIVAcbqfVMffB70x8Y
rdgPqAKBNfAjRgCswr4LX1RVa9DKq30+4+XveP3zRwqod6kAKMAWyEfqVpbgLb67XaV4lQZW4WMjrDms6t+PfqAGxwQ3B6lA7R+gEG9XQWRv1QOWmwNjZac6
7IaVm9pSQAu0KLTYd7W3lHBV+G2sav1W5wSzt+3jxd+1Li2VTPhOruVUFaVkNlcJh4S2Db+Nm8HtXap9R4Gx3fQSOdP6XgH2Io4E3uCt7Q5OiJ467+9MSLT3
HRD1TvJTSr1ZoUKZ4HrYVWGogNY2Zg3MPoUEaN9Rtp9XGNUHmnBWcI8SRAWKA+dtwIjTXxb/be1jxtC1fdcftZ4Jh5XYC8dEDT7/6/1Wq0dVURwWIwQXHFoc
1m14XWLVOr39Ol5Tf4gNJ/xZX0FEBTZIKeJ/i1H51iCZaqL24bPgktGR4GUd18AEfL3p9fpPb2viTmeYh5WdAb6FeDjiHQ7jTFVrnu8RsRNnCzhI9T2rTQxm
SkCrRws5HM71/hGIqj3zeiaEk3AKZEZk8D4aXA6fP1cU64ZJL+sru+3ltgfS+6SqHI/aR5MqNra1vvqe48z7afDb96m8V2ltG07qu3xq5YmjMHXOgZurJ9dV
whdr5dtI0Ypw6693eq5m6/3ZpayfxOk3ZyIbmMS8I8HrNiDZkflgzQe/ALBB3xLjblfNJAecU3nfiZDSZkIgiawAmo3Tc8WfKhnFEczXJiKYE+V8wMQIWjQb
AfAdBWYSZZsAVCnN/b5LML43H3jDSy1rvwkwv9pgq0u2ggleu7clQAgYoOJQVoaqY+eSi521DtggELiJy2udFZYJQP6ZDb6Pj3V0Qqjd2eI6r9Xqqv2f2Te1
Dl7eae/49Hy7jPOFEzeb8nYnQnNCYF1GLK7GZpwuVSoY4TkscFzN25/acsLnU1ePE8yE1eA1AvNPbdc64LDANYgRNJyoCwmpjoUaU8GlpxGu9+lIHSjevwnH
JGbiguVJH8QP++Z/nUBFFIFteLdtEOb6u0yVVuq1chUoK05geZ/lWdSfwe8BE5L8M0ecfXw4RAHxKdiR+viuw+hPvC7CUmGuL091831QFWGSEBOzUbJORGyw
q6I4cv0yQ3zLFFC2VuuZD+oMXzCm00q07I0TabXXrH2qzO1PJXI1O/KoWtVp3Pz39L7dY3Pe1IQ/5U3i1uUH+1vbN3xBCWMQIaK1THYKn7KiOVL9TRZxKnV4
nfY5YZ2Gz+4bQJgTQQWa5bwdB4FI1Wk2PC/nlW69bxLL2/BnjzRln1/i9fGdSph1wNnnaaAMdpaYweHv8QmvYjZZbcD+8L6YGj+1WqJtIkIQuhsEkCAQkYnQ
lOPiKhmVue2+GemEc2YDzoXAFuFvaxDe5rucxc9g3urnREw+hi5IBAoVjnlsHn39jZU73I0FIuaIN2Z7XNQHbfuSbXFlN+t/R+5xXIFpsOpjcT+OEcbsdS/r
ZfgX7IMR2AQD369DpPaf23r1cmaYdUsVWuHw62g/7Leyjfn9rW5b5WI4ChA0TcRqtcLpSy7Bf/qRv4vTJ4/h/EGPvcMBuc6OHSqFj4io/zdn1CNo5sxrem8O
B1FiwsNuzdE1+zL9NLcLSCT1vfpthkv7GuOjP+fGrQezS3XG9FuNWvktgB2YbULYvh75AYljgmHuHKQUJDAkGjHuNooSqRwOCRAATRA84bGXYbVYYP9gPdl4
DwPN2px1f+qFEeq8j/bFZPEM5gkf/v4WPVapBYQQ0HVLnDh5EU6fvhQnLzqN5XKJb3vtc/F51z0BL3jmNTh1Yhf3P3AeF/b2UXKqsFhl/F2Jmv8RNxOYJMCj
/XVQJkrkeAkLOyHP8M/fqPibGcJbZay6rdtGXH7TG5pKOLLmUPLrhDDemX7Xd6zcJNpZrsJ4tOd2EQSrpXqzTfp4R4WooeSKQIxom4inffZj8G1ffwP+3te8
FKE7hrEoHnroHMaUSIhW8yS1XNR7w/Z7JsXr4Bq8U08MLoMleP1VankbVFfLxQIXXXIpTl96GXaPnUTTLhBiBDTjDS97Jtq2wYlju/ica6/El77gOpw6vsKn
Pn0f9vb3J7iMLuaom0cUpm/eJ3t1RgjAbOjsO9XgbPgNAfw59ZbX1GfCMpH//P+JuGbc5dfUgSOAzS41gLY7ixlAsydGUXyidTCsd3XwK7hzyWBtSO0Ykdo2
ESd2Frj+2sfgu77hBnz3376rkWUgBgERQtUOXnZGkMBogj2Dzf4jbfdjF/6rf+Nv7r/IQQIfV/VU4+KQwUH2wbGkOxjPdlL3kf7Mf0vYRofg8VL+a2j7ykU0l73tVUObQHjlwHlTanM
ZhUg10yi0cs7gdX/+KfCd2Q2NXsoszpjjDh5bAdPevxn4W++4gvw/OufhADQHxSpVujTISeGYEa1CA7WPf7v/3UrPn1mj/UKUIqiac2XZDZfgeIvP3UPbr71
o3jw7HmgjPRBVdgmlYMQgRAgTYuw2kG87DLsPPtzsPOsZ0NXx1E00tZZX8DBv/opxL09xK7DYrlCjBECEs1UtVZs/9HPfztWi45EAkVOxQiY+CiZ6lIL0DUN
JArymHHuYINf+f1343fe/kHcc/9ZbDY98WF4NBnM5ubjOxubGeZr2Ymx/bfR1YzQ/VJglgrkNqggNo96xmy26ABVwc/OGc3wJ2v359QalfYhMn23F3hZg/Pb
hjv7OEEK2qbBFY+6GF/4uU/FN772S/B1X/5CXHPlo7BoIsaUEQRoGqqMqTJgGDPGlBBCwLofcctf3IsHz+8jl2LuC5gTEXSOmmF/4tguVsdP4NNnR+RcO2pQ
qc32MqSJaC4+jZ2nPR0XvexLcNHLX4blNddC2iWa0KCRgAYKaEL/nvdA1huUXJBzMttpe1xEAAmUVF//6ueibSJSJnxmt5N5Cs2DUgr6MSGXglIUm35E20Q8
+ymPx3OfdS0uPnkcFw7WOLdHOxQQyzYx06TqGrtmpgT5aEZA6k5u9wIQAwLvJBDjZU+/scpKvwxxgNc0IWfroTXoCKOqcADmwNIReOVnXYKvftWL8Y2v+xI8
/1lPxmWnT2G56AxQQU5meBt8pRT+Nb+H4bOC0TSBKlELuiaSC4Mg54xSFDffcTfO7q0t+6TQSPa+2AiVkiEi2F/3uPuBA2QFdDb1Xnz2VVheebklxrnpaqrQ0WNf+EwhecTm3e9C2PQ2vaK7QTheLKOEQUG7742veVGtLWfOFAWm5g3WEOiacIZQLWiaSMISQD3YDamTgJwLUio4dXwXT3vCY/CyL3garnjUxfj0fQ/hofP7U9wVbMOwXAnFx8JhEwW0Thm9vZktZl9EBEHhvpbZZ/6vSh1WMv21
9yz9QgSmo516gRADll2Dq698NL77m1+LX/up78Ibbng+Lr/kIiy6FgBQSkbWgr4fUTSjaEEuZnPA8ulNAgYzcoMIUskYxymUI0EwjCPSyNliLkA/ZIxDwjgm
5FyQUyLYZRps+scEEiJdDRCgZCCPQOpRcsKQgayK7Hl41j8KN5faRLPXD1WgJPtkiE0iav7UHFfKxQxNjIQz0xeWckFKGWnM9Xs/jGiagDa6WVAw5oyUmOTI
FHWqxjElpJQBAVImEy0XC3z5S56FX/6hb8S3vP5LcMmJJWIw2CrrTNnA7JMReu3gbPznInz2jnomqhMYp+n+fVY5i8++GoaVCWlQJrMJqApDEFxy6ji+4BnX4Hu/5bX4hR/6e3jNF/0NLJqAJgYsujjlAwFoY0AIDIvkTEcg7QyDTXw6XhBsvVLXNNVP1TYNbY5I4shFMZaMnLMRarYZFokq5wwtNlv0BSEiEFNBjPeRKFQLUgGyqVXncxKZEZT9dRUCk1RaMjRnEqv/rsmXflEKNkEQI4ngYNNXqW1cBVUSH0NcWl0bbdOgjZHe/CB1YqOFRr8aQ/RDwnoYkEvGMGa0TcTfuuG5+PWf+Hv45te9FE9+wuXYXTZMC3fJY1pp7l5y8qv0YR4GCqU5GSliuPSpk5+Lj7c4cW5D1TJ2a676XCN+1mUX44V/4yl4w6tegNe/+kW45nGPwXLRVtTnrBAJ1QlKUR8wpFTDHyEEBKF6UwCaFU3TVAM2pYKmMVWgpRKlS5FSFMM44ta/uBfn99bQOpj+vEBN0qoqclHsbRLueXCN5KLJGGxxzRPQXnkFZB4ghnfY8OxIV4aCtIzYvOddiOs1mL2JaYGGYZb3Jqfv3/nKL6w2Zy60LauUVLbHflB60wQgvrw+Mg+flaKIQShxE3HkzNTEUNOWlm3E9U95HD73uqtx5aMvxsF6jQv7axunGUkZMTnz8At7wf8nWnGpPK1bnEsrdXRNqrI2YpdzlQRBCIrLLzmJv/vaL8HP3PhN+Adveg2e9sSrsFotOCsbE0qmPdVEsmFOFNNQEoO7E0RAqaKc/bg9IUYUxaWawZASXRbzdkQY9A1BACNkhSKXXF0c2VRJShmbvkfJTIuB2mxqTggz9HCCMX3PFo9WkxDFyjspEpV0jDpeVcnejltVSk5KCmZ6cEioCoMRA/ssiEEYS51NeKCKlCihcyEOaLRzlhnM+M+Zs89+TBjGhCCMHDzmsovwFV/8HLzle9+EH/z7r8PnXHslGnc8V4I5koE6vwRHaMVdL/X3jDsNESI+KzDOM6INIWBnZ4Wrr7gM3/b1X4Zf+anvxpte9zJcevEJhCjY2VkBCJYpEJC1YEgZQ6KHOTaRSLD0lOCcaQ7JbPaCqiLEgGFIRLKVS8kQH7jGRF1tqSJGIArQhABxjvU+qdLIHRM260Pk7OnACVrSlOcuqLam0xrxRoOadhvr1MKwDAloIrYJjy4B/L4RVckoJZFhQN8T1y+YjSmCro015ScGSstgTmW/hiFVN0wIAYEjDZiaHoaRPjKlXxAKNIHOWwk2w44R/Zixs1rgCz/3SfiF7/8GfN+3vAZXX3EJdlYtmb626P10YjKGA4C6cMMXxc5F+5GLxilfEChCUFx68XE8/zlPwfd881fi3/zwt+G1r3whLjq+axJIgKKMf4E2hCrDHKUomsCZWN/3CIHiO+eMGCO6rq1r9Tz+JxaobdsILSQMLSR4NZdELrm6KRrj+jn8pXCNAP1L5G6AyMkpQWw2Sarh2sQqxRxxRlhOPKxzRkiObBddftMyJ0hfZpMZfAqDyyTq4WZA1oJxzGQiW0MKMz2coA/Wg/Xb7EcBkrlmNpuRNlqdWAl2VouK02HkeDRNsOwRRcrZfGgZqRSsNwkK4GXPfTre8n1/G//g616B5zz1cTi+00J8qZ7Rtttj87m0U1OgSPWyRIpTI8yXIaaWLrvoGF75wufgh/7hN+AHvu0NePkLrsfFJ3bNkCan0YPsTksa2QEkEMBy0kPAPWfOutIxDiBR+SUilGIW/nAXRYycjqfEkSXBENGwQDD9Wm64T6qCatXEeimIIWIchhpUhmZOUEq2RRDZ1vvZvGVmJAPm8TYiq7RZXMjzPfbQ6K1aI5Mq86EQoZQPIaDrukqfxZijeHxRqfLaZnIwx0hDXkJAypmw2NOSM0KkOdJatq7a2AIkypQ4ViKCvh/RDwlDyhhTwfHdJV75wuvx5m9/Hf75t34VvuBznoRjqyWiwcqqGKetbg2T/jZk7LAD66CJkNdOnziGr3nVi/HzP/Qd+Cff+tW47olX4vjO0oqZ9CkFm37Euh/RNA25VGjbwKbCTJqjbfBZl55GP4wYzfYqNlC0k2hv7R0c2oqYgHHMKGY/FAtEl1JwYf+QsCpVQj8mHKw3aGIgN2aL52FyNAZTA00I2N1ZQaDQnGxml5jYVwpgxOkDPUkq+p50NmmfY4/+NGdUm0XLVAmJqf5HpglUgU1kIDub8R6Ns0sxA1uBrg2QwDpjDEjDiPWmR8kZuztLqNI29SuNGWfP7WEzjFWCrTcDxjFBhL6+vh+pbgEsFg2aEBAjiScG4NTxHXz+M67Gm7/9K/Hj3/16PP2aKyCmAeBdUeMik2WB6/WIHs5oDDEoWDQB3/ENr8J//Il/hG/9Wzfg8kedqpJkGJmAVwrDKqqKtm2ws7OsfqWUCpL5bVKm6ipK73vbMvdquegQQ0A0x2UpBeOQkMaMi08dx5ASCcsk6jBmE8IAILjs9Cl2LAjGxHe7tsMwsm0SFAcoBJjHmwMVI+21Os4urdSlFzmSKlBJUApKHZdUkzfGiMow6ASGSSr7Yy41YyHSjsUqbSYIMcls5srheqjuCAX72fcjHbsKxKbB8WM7iBYKCiFwfMywL6o4cXzXJKdisx5InDZTBwLdHC3DT5RkNMijiZ8AYLVoIRB87lMfh5/93jfiJ//R63GsteiO2YrsO2kiiNsB9XIdKjjWNfiGr/pSXHxiBzkrsiXcuYRIFlyl3i5GVNkMRE6TN/2AYRwRA1UPEUSEqhLRpRRkE/cKoGkbpJzRD4nxxMZcFELiCIF57QA4y7OZkaqia1uEIMglQ6o/ioRZ1PxVmW0WLQgg505qykVUAWypPonKYLfHldAmTVB/k5Bc9ZGI3HadiIxWEd+ze0Z9WgpiNJ+fTusX/c0QArqW2gFg7loUOlZdSi8scyQEun+GMWH/cFPrS5nSKifaUEUpZgSEJ2VqCgXHFiIoWdG2Ef2YEKB4yec9FTuRiZdEglMQr6AmEUhgBJacTpW2GTO5volY90NVS23boGli5VamxQAPndz...snipped for brevity...U2Z7jzwhh9myrHev+/MZ2u07IPhDeD388MZ86bT1CnUe/bvd0ghegg5o9OorFoxdfEOs+32fjlMLbV8XSNrp4+btzCQvd6gzHag67l/U7zJqblgU58moBQ5aYOJ4hg5/p29Gqj3amDqVRQSVGG6hpqCYimDo9cVaFwaQFrwkJlUFg3F3rn6mLR3zXuPMz+OmITPv310gBPiHaiTtD31zqYwJx+rkNtw+cQqtUmth3VrZWwr+VKB+pxMMEwMTMlShnkPgvrfUe8c/VUePHy3p/za3LBa72+lRtJV6roM7U7K+JjKkpQqEPI7bZcM2IZKIrB5D/13cr3FNtWh/UW9PA1WDwNAgmk/lufW8edXBpZJVt98auOVTTHV5zdUGcVCKeXU64MxDmT+HDBEy2YC0yg3UbvqmfW7/UMFVxbX8r8UwMh5mvYAKJD2sRf6bKaEStmnjzPjnzkYgV4Sin2vBVQO3m7G9tqs7QtvE0IWp6zWl6qtfoco4bYC6s6q0jRDGvx96vsHpPDS7C4O/Orxly/Xe9jkLwyPf8jveNMFDCq3KGXLl8jgyfwGAioq2HR67aL1gx9b1fcQTLbLe+AyJoYiJ74q9UPxHf4W3rx5wmTKZMktcmE8L+Ou7F26/04NtWut0ydXu6ZgBPquGR0DBd4rB7Y5U45qiYrjmA0z0SEjs7e1AhqRh5xMs7yD9TIa8TRrSOMPHiFu/jOw+vfE6sc7BYemIi1AF5+DtbsB29rMBW69sIOJIEaiXtL5lqu9+1vaPjINPTWsTLVQI+ctmz7frY9lx5w+e+zuOYVWag2i+/45Xz45SqcEQaISnPsJ7XVYHyP94Bb8Ly6v3+NPCPgJQZgVQ2nh7OYLV2vYBVNysIALPYqZf1PjmcDsNU12wIP8PFp86MDx+l+WUPnYhql4wVttonYE64D6vWq7K2OT7Tu7xv11adfnOGzPqcn4pzf1bhmsGoU2X/L1JyYgZ4kJRbAAAAAElFTkSuQmCC
"""


def _walk(root):
    stack = [root]
    while stack:
        widget = stack.pop()
        yield widget
        try:
            stack.extend(widget.winfo_children())
        except Exception:
            pass


def install(base_module) -> None:
    app_cls = base_module.ThermalConnectorApp
    if getattr(app_cls, "_turto_branding_300", False):
        return

    original_header = app_cls._build_header

    def _brand_window(self) -> None:
        if getattr(self, "_turto_logo_master", None) is None:
            master = tk.PhotoImage(master=self, data=_LOGO_PNG_B64)
            self._turto_logo_master = master
            try:
                self.iconphoto(True, master)
            except Exception:
                pass
            try:
                self.title("TURTO 3.0")
            except Exception:
                pass

    def _branded_header(self) -> None:
        original_header(self)
        try:
            _brand_window(self)
            header_img = self._turto_logo_master.subsample(2, 2)
            self._turto_logo_header = header_img
            labels = []
            for widget in _walk(self):
                if not isinstance(widget, ttk.Label):
                    continue
                try:
                    text = str(widget.cget("text") or "")
                except Exception:
                    continue
                if text.startswith("TURTO ISO") or text.startswith("TURTO 3.0"):
                    labels.append(widget)
            if labels:
                labels[0].configure(
                    text="TURTO 3.0 | Izolační nosníky a smykové trny",
                    image=header_img,
                    compound="left",
                )
        except Exception:
            pass

    app_cls._build_header = _branded_header
    app_cls._turto_branding_300 = True
    app_cls._turto_brand_window = _brand_window


def selftest() -> None:
    assert VERSION == "3.0.0"
    raw = __import__("base64").b64decode(_LOGO_PNG_B64)
    assert raw.startswith(b"\x89PNG\r\n\x1a\n")
    assert len(raw) > 10000


if __name__ == "__main__":
    selftest()
