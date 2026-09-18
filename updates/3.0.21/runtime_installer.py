from __future__ import annotations

"""TURTO 3.0.21: source element length in decoder and exports; existing customer files are read-only."""
import hashlib
import os
from pathlib import Path
import runpy
import tempfile
import time
import urllib.request

VERSION = "3.0.21"
RUNTIME_LAYOUT = "52"
REPOSITORY = "jaroslavkucacz-code/TURTO-Izolacni-nosniky"
BASE_COMMIT = "00fce83b4abd9912dbf26c113b798c6670fa9241"
BASE_PATH = "updates/2.2.46/runtime_installer.py"
BASE_SHA256 = "9c9a435923c0cb4514dedeaaf06a10fb743c3b4201ed999d36b63ee617b2bad2"
MARKER = ".turto_runtime_3_0_21.ok"

PAYLOADS = {'app_runtime.pyw': ('cc4d74e086b55e32ef067dc223a7c3e5691b052f',
                     'updates/3.0.21/app_runtime.pyw',
                     '6cdba51a56fc9c7af67c6610678e3892cb74a582c25677c637f83652e29dc737'),
 'branding_301.py': ('c396b4d2e7c7fafc3e40e726b29456f6ed8d2f0e',
                     'updates/3.0.12/branding_301.py',
                     'c1bccb41ea87278a4598b4de80370da3e8f207d577e79be2d29a6630094a92f3'),
 'iso_bulk_301.py': ('e2a04fb52d2f344942e00686206bd4faad7d66be',
                     'updates/3.0.1/iso_bulk_301.py',
                     'eff6e5b0b6c7cfbed756ca4b2109d895f8cb565b7f39e1935a252627b3f1d192'),
 'turto_icon_301.png.b64': ('0f7e5c11bd09c843ff105eb10a9b1b64fd168117',
                            'updates/3.0.1/turto_icon_301.png.b64',
                            'd98c9ae427a9837b038bc3b9352fd13c3e563a98d4e85ff4529fdc7f7d7ed11d'),
 'app_runtime_246.pyw': ('1c1427a1695f529db0d720d576cbd3c0556a12a7',
                         'updates/2.2.46/app_runtime.pyw',
                         'f9b7647b35b6d33d1aad7222eda0dd6573cb6ce882f942a71645f90a8ae3a5b9'),
 'bulk_import_engine.py': ('2ae47d6810a842526234b995843319a9c367b400',
                           'updates/3.0.20/bulk_import_engine.py',
                           'd26ba8c33a1a053c6c733ed6898f10155dfd1caf0d9c0d3390e701b6ea126dec'),
 'bulk_import.py': ('2ae47d6810a842526234b995843319a9c367b400',
                    'updates/3.0.20/bulk_import.py',
                    '51ba55af391918560077af5ebc3b6d44e344dd0bdd40d38b79447f2b2724462e'),
 'catalog_engine.py': ('d321d428680ddbad888ed8eaad385d6ee642ffff',
                       'updates/3.0.15/catalog_engine.py',
                       'cfa49b857cf2223ea5161be3fbca3054378bf4c0a7361d1d5aa243956427d67b'),
 'runtime_paths.py': ('d20446e502a87aed46326d810ca000ce1d69cd5c',
                      'updates/2.2.13/runtime_paths.py',
                      'd25f98aeed24d866cf6b9f8ed63833d45e65252cf070f06600a91e61ec0e025a'),
 'isokorb_xt_parser_243.py': ('d20446e502a87aed46326d810ca000ce1d69cd5c',
                              'updates/2.2.43/isokorb_xt_parser_243.py',
                              '680f6853fbb62234a440c2a43e8d1b4f0b03e0df2b4d69c4b84b6b52a2a28352'),
 'isokorb_xt_resolver_245.py': ('e7eaa0dbe2b258f4e2f6d59b635ecc7393679bb5',
                                'updates/2.2.45/isokorb_xt_resolver_245.py',
                                'e0a633936c4d901aa9fa88f89b50fa85e55e6eea80a43b2235a743117144dda7'),
 'isokorb_xt_resolver_246.py': ('da091c489678cf8da745190785a9988757072d7a',
                                'updates/2.2.46/isokorb_xt_resolver_246.py',
                                '3b7407cfc3affd947fd9995a48278e3e97b194d6073111b44eb192e375941218'),
 'shear_cover_302.py': ('e6a90331abdac9ed952aae6936c7adab66950b08',
                        'updates/3.0.2/shear_cover_302.py',
                        '626e762b50e9d9f2562ccfce95560d5cef8af1b7c7917c08cd6f395a14f5fa9c'),
 'substitution_workspace.py': ('b0cf7a80dcd741c1da8815b99eebad010d827fe2',
                               'updates/1.1.17/substitution_workspace.py',
                               'dcfe3fa70fb4748c29216c35bce610681fe787331908a219a2f7ba9666082301'),
 'substitution_guard.py': ('b0cf7a80dcd741c1da8815b99eebad010d827fe2',
                           'updates/2.2.6/substitution_guard.py',
                           '81854ebef393b1ca93e51be9d44019caa3815f37482655d2ba3e96223d570486'),
 'zvx_tables_303.py': ('2e958a86ece1b621a8457e98ead4716781468201',
                       'updates/3.0.3/zvx_tables_303.py',
                       'f3ecaedb4a0611c8023189a417592f8d22c42f051128d9ce6b44f242e3a263dd'),
 'zvx_annex3_303.json.gz.b64': ('6560e6d8800fb5f999fbec97fa91dee120256be9',
                                'updates/3.0.3/zvx_annex3_303.json.gz.b64',
                                'd43c34055048041a5e724a7a3b8d50a8d8601932614d2549ab015d9870aa1eb1'),
 'hit_core.py': ('908d003fbb6350d87cbd212c17650c754a6542d2',
                 'updates/1.1.17/hit_core.py',
                 '8d7666fed0e87a7cd06109669090eba060a614f6b34f282e3e61a8c5be334ab1'),
 'isokorb_families_304.py': ('b6c85b785631628b4de9592b22697dadb14eea8c',
                             'updates/3.0.4/isokorb_families_304.py',
                             'dde6ad19e0d0737600fc54ad11306099bef3d8ac3e7b848ffb346eea4bb8615c'),
 'pdf_data_304.py': ('2ae47d6810a842526234b995843319a9c367b400',
                     'updates/3.0.20/pdf_data_304.py',
                     '35d2b42ace3483fc88f56c6e364ff4b464e982aefc7511e74a3b9e4c322f7ce7'),
 'pdf_scope.py': ('7af0f6347f4dd87801a7697bc24347198d0d8cc1',
                  'updates/2.2.9/pdf_scope.py',
                  '68401d779f3bc97c9473a50c82c91db0c46faa7fc1d64c0b43e982a5d62a748c'),
 'pdf_context_240.py': ('7af0f6347f4dd87801a7697bc24347198d0d8cc1',
                        'updates/2.2.40/pdf_context_240.py',
                        '1556963fc2261fa83e3943283e1ee0509aa73fd602ba60986038672c74caeba1'),
 'hit_pdf.py': ('7af0f6347f4dd87801a7697bc24347198d0d8cc1',
                'updates/2.1.2/hit_pdf.py',
                '62909e7ecbcc5f56d7dca077cf95421cb1ee10931599433557abece32d629ea8'),
 'hit_pdf_127.py': ('04deeff098d6aad06ae44f51fb49092bc6bacde3',
                    'updates/3.0.19/hit_pdf_127.py',
                    'be2c61ca04a838643573fdb756eb34bb471fdd4ff100b412bb475fee1ce69490'),
 'hit_pdf_prev.py': ('7af0f6347f4dd87801a7697bc24347198d0d8cc1',
                     'updates/1.1.20/hit_pdf.py',
                     'b3e7072297cb934acb762bcc99425f2669ad6e0b9e50ff87c50280f9230eaece'),
 'substitution_pdf_base.py': ('7af0f6347f4dd87801a7697bc24347198d0d8cc1',
                              'updates/1.1.17/substitution_pdf.py',
                              '74a4cb629ecd39084374b77467413f6402cd638ae10b8f56c256682898c13883'),
 'project_model.py': ('2ae47d6810a842526234b995843319a9c367b400',
                      'updates/3.0.20/project_model.py',
                      'cada7064a452365d119ca813aecedc267152f2009ecde4e05e08e7024fa8efb3'),
 'pdf_branding_305.py': ('f3993a50d2a79e51e1d88994e056a6c88d9a7931',
                         'updates/3.0.5/pdf_branding_305.py',
                         '70d86c6238d1cffffab69c251c2f45660d23a8dfcd932821811a94e85808bc21'),
 'turto_pdf_logo_305.png.b64': ('f3993a50d2a79e51e1d88994e056a6c88d9a7931',
                                'updates/3.0.5/turto_pdf_logo_305.png.b64',
                                '71a0ae5f632a57e7dfe4204d3f0d494071024e53a25a5850e66481b9875c7d40'),
 'design_rows_306.py': ('9c58481ed5ba8dc311f241e55670b91d62afd6b1',
                        'updates/3.0.6/design_rows_306.py',
                        '1ceb657e4686ad6eeddf45b0152b30a4be8b6999b84530d880126d88567f43dc'),
 'isokorb_qp_307.py': ('4ca42cbf8d075f0e7dfbdf98c0d0c73eebaa4746',
                       'updates/3.0.7/isokorb_qp_307.py',
                       'f7acace87edcf462add4e803e116e281d4b97f2a8c7f68bf627ce0992931b88b'),
 'schoeck_t_qp_307.json': ('4ca42cbf8d075f0e7dfbdf98c0d0c73eebaa4746',
                           'updates/3.0.7/schoeck_t_qp_307.json',
                           '018c43c96eca6825606a930a6ef354e6d0dbee57b74efedc2d5f14ec9079b4ee'),
 'shear_cover_308.py': ('f005b4246949fb308e48e890c48531e8daaf1961',
                        'updates/3.0.8/shear_cover_308.py',
                        'c74a879a7ade048589f4feb02245fe342395b7ec75ed446063f04e5c006cc13a'),
 'hit_choice_309.py': ('f079e59e4b7dd22c1778594f1a6fd66f71ef5332',
                       'updates/3.0.9/hit_choice_309.py',
                       '893ebe7a38a78ebc87f845ebd987f0555c2416e94a49f2252cb811bff1863f6b'),
 'hit_units_310.py': ('83871f6f21a8d802c7656a795de14c46863f2265',
                      'updates/3.0.10/hit_units_310.py',
                      '8c90d24c0d8cf9bc55001b7825d166916fb9c49c5fd9ddb18675c1a6d7306f61'),
 'hit_excel.py': ('83871f6f21a8d802c7656a795de14c46863f2265',
                  'updates/3.0.10/hit_excel.py',
                  'c9462e64aefefb0a94c10f6cff54f3424fbcf97d2de1e25cbc072ca32421f626'),
 'ui_responsiveness_311.py': ('75f9662999ff85bfd37ef5310821759dc643d3a6',
                              'updates/3.0.11/ui_responsiveness_311.py',
                              'fd116665eb11c4b9e2001b28de607e9d0b4a1ef587c6210528806e9adfbd87ec'),
 'table_controls.py': ('75f9662999ff85bfd37ef5310821759dc643d3a6',
                       'updates/3.0.11/table_controls.py',
                       '41754408ca0d031a1b607b86efec1b192043924101d0693031227524ede0a039'),
 'hit_virtual_scroll.py': ('75f9662999ff85bfd37ef5310821759dc643d3a6',
                           'updates/3.0.11/hit_virtual_scroll.py',
                           '13f5599d870e01aa1d6bf1a37c5fc5757ee53d9e4d04fa83e2be4bd9721addd0'),
 'decoder_315.py': ('24f83758b5c23df5c05e255076e1e51a9b5d851b',
                    'updates/3.0.15/decoder_315.py',
                    'd6d28bf0d291108661ca7bdb42413dbaf5cdb811f0e30bbf5f93a85fd98b066f'),
 'isopro_2018_en.json.gz.b64': ('d321d428680ddbad888ed8eaad385d6ee642ffff',
                                'updates/3.0.15/isopro_2018_en.json.gz.b64',
                                '560d7f70f90e93285cd4010a05633afc87da6dd0afa5700c20d9b1c8c83c4b0f'),
 'schoeck_cz_2024_1_2024_09.json.gz.b64': ('d321d428680ddbad888ed8eaad385d6ee642ffff',
                                           'updates/3.0.15/schoeck_cz_2024_1_2024_09.json.gz.b64',
                                           'd90cd37a97bc3b2f955b6ffdf4c6c4d25f1d3715b332625a58e7f90f8be94043'),
 'shear_dowels_catalog.py': ('f74bd1515718dc167ecc0c4fd881ced8527f49c2',
                             'updates/3.0.16/shear_dowels_catalog.py',
                             '2eac1519f8f98f01f722c8a5c2d4dbf8cb549346475bff2e1ce89bb2dc03be94'),
 'schoeck_dorn_decoder.py': ('2fb3dd44a7180ca8550b169bcc737c00efc3a2d8',
                             'updates/3.0.16/schoeck_dorn_decoder.py',
                             'd517c335219ebc68de705e4e43ce9bf70e089dde4bf3c5732911409539a1df1d'),
 'shear_capacity_317.py': ('02534506bd62606728f4494481ce0778987745ed',
                           'updates/3.0.17/shear_capacity_317.py',
                           '7614155706abab32c195aa32bf468351ec3b7ce9b6dd1626596cf5388eb8fb00'),
 'workspace_controls_317.py': ('8ebac5e14fb7ad0d632033092e5ad4ed1656f89f',
                               'updates/3.0.17/workspace_controls_317.py',
                               '205cfe7631a2c4b98b0481861e783ae646db1d8f8347c8530b9fda9bcb18bc7d'),
 'shear_workflow_236.py': ('02534506bd62606728f4494481ce0778987745ed',
                           'updates/3.0.17/shear_workflow_236.py',
                           '6b76b22e75912470632b802d4c368c24d4f154bffee7e1a43c27e6a95e8503b0'),
 'shear_schedule_io_236.py': ('02534506bd62606728f4494481ce0778987745ed',
                              'updates/3.0.17/shear_schedule_io_236.py',
                              'b3063e5754c15389cee95783755b2827be997a304c1999742a212408134dde31'),
 'shear_choice_318.py': ('51a3cf7b1a464219241b23114d7b85295edf56f3',
                         'updates/3.0.18/shear_choice_318.py',
                         '49b1119614edc750fe441616c4331f45f092a81eccc17a9d696cf0160ea2a596'),
 'hit_wt.py': ('04deeff098d6aad06ae44f51fb49092bc6bacde3',
               'updates/3.0.19/hit_wt.py',
               '640fbe9d73dea2ae31c64d9e3e00507ba2c44c31c77b5232b88ecdf06f0800d8'),
 'hit_wt_ui.py': ('04deeff098d6aad06ae44f51fb49092bc6bacde3',
                  'updates/3.0.19/hit_wt_ui.py',
                  '6eda7d6f66c4094534f4d4ffb49a9a8a544a0d65884428bcab10fb7c84cc1aed'),
 'hit_export_ui_127.py': ('dfa81d957c649148bc17e7cd54de0f043a1ffa7d',
                          'updates/3.0.19/hit_export_ui_127.py',
                          '3bc63343df01f0836c07d62a588088bd64d3e9307102c6f1981592df155f9cad'),
 'st_workspace_319.py': ('dfa81d957c649148bc17e7cd54de0f043a1ffa7d',
                         'updates/3.0.19/st_workspace_319.py',
                         'd35dcd346d92d7eb386dbfafff7cb7bf2f38e517eb9c99fdeff8f7cd7d9efefe'),
 'readability_319.py': ('04deeff098d6aad06ae44f51fb49092bc6bacde3',
                        'updates/3.0.19/readability_319.py',
                        '6fa64aaf406234ff2d0d69351a6de32ea2f3bcd86ce0e5dbd9f8608312d5d5ea'),
 'decoder_length_320.py': ('2ae47d6810a842526234b995843319a9c367b400',
                           'updates/3.0.20/decoder_length_320.py',
                           'e92acf38687dc2fb94399c09dc14e9990b1a14a2ff1d15a8766eaba87ee8bf07'),
 'decoder_detail.py': ('2ae47d6810a842526234b995843319a9c367b400',
                       'updates/3.0.20/decoder_detail.py',
                       'fb6a6c0de4206ead6bd333fea175cc8393727571b0a36ef9a219cbb20485db76'),
 'project_ui_prev.py': ('2ae47d6810a842526234b995843319a9c367b400',
                        'updates/3.0.20/project_ui_prev.py',
                        'e929e4585cac89e4e2f482e578abea312eabe4c9e44dae6d5991f0d257e4fdcc'),
 'project_ui_base.py': ('2ae47d6810a842526234b995843319a9c367b400',
                        'updates/3.0.20/project_ui_base.py',
                        'ced1ac409c3ac130184afb6ac5d8400afd1d652d390d702ac4aac3d4cbc65b81'),
 'designation_format_321.py': ('cc4d74e086b55e32ef067dc223a7c3e5691b052f',
                               'updates/3.0.21/designation_format_321.py',
                               'e19003c94484f5edc86f37ecc6afb55e1c240c44bce67b4e4467bebb02d9278f')}

BASE_REQUIRED = (
    "app_base.py", "app_runtime_244.pyw", "app_runtime_243.pyw", "app_runtime_242.pyw",
    "project_ui.py", "project_model.py", "hit_workspace.py", "platform_workspace.py",
    "action_workspace.py", "action_store.py", "action_payload.py", "updater.py",
)

def _digest(path: Path) -> str | None:
    if not path.is_file():
        return None
    with path.open("rb") as handle:
        digest = hashlib.sha256()
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
        return digest.hexdigest()


def _revision_ok(program: Path) -> bool:
    try:
        return (all((program / n).is_file() for n in BASE_REQUIRED)
                and (program / MARKER).read_text(encoding="utf-8").strip() == VERSION
                and all(_digest(program / n) == v[2] for n, v in PAYLOADS.items()))
    except (OSError, ValueError):
        return False


def _download(commit: str, path: str, expected: str) -> bytes:
    url = f"https://raw.githubusercontent.com/{REPOSITORY}/{commit}/{path}"
    last = None
    for attempt in range(4):
        try:
            req = urllib.request.Request(url + f"?turto={time.time_ns()}", headers={
                "User-Agent": f"TURTO-{VERSION}-runtime", "Cache-Control": "no-cache, no-store"})
            with urllib.request.urlopen(req, timeout=45) as response:
                data = response.read()
            if hashlib.sha256(data).hexdigest() != expected:
                raise RuntimeError(f"Nesouhlasí SHA-256 souboru {path}.")
            return data
        except Exception as exc:
            last = exc
            if attempt < 3:
                time.sleep(attempt + 1)
    raise RuntimeError(f"Nelze stáhnout ověřený soubor {path}: {last}")


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".turto_317_", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def install_runtime(root: Path | str) -> Path:
    root = Path(root).resolve()
    program = root / "Program"
    if _revision_ok(program):
        return program / "app_runtime.pyw"
    database = root / "actions.sqlite3"
    before = _digest(database)
    # Stage and verify every payload before changing the existing application.
    payload = {name: _download(*pin) for name, pin in PAYLOADS.items()
               if _digest(program / name) != pin[2]}
    if not all((program / n).is_file() for n in BASE_REQUIRED):
        with tempfile.TemporaryDirectory(prefix="turto_317_base_") as folder:
            path = Path(folder) / "installer.py"
            path.write_bytes(_download(BASE_COMMIT, BASE_PATH, BASE_SHA256))
            runpy.run_path(str(path))["install_runtime"](root)
        # The base installer may have replaced files staged as already current.
        payload.update({n: _download(*p) for n, p in PAYLOADS.items()
                        if n not in payload and _digest(program / n) != p[2]})
    if not all((program / n).is_file() for n in BASE_REQUIRED):
        raise RuntimeError("Nepodařilo se obnovit úplný runtime základ TURTO.")
    targets = [program / n for n in payload] + [program / MARKER]
    backups = {p: p.read_bytes() if p.is_file() else None for p in targets}
    try:
        for name, data in payload.items():
            _atomic_write(program / name, data)
        # Fail visibly for a corrupted logo instead of silently ignoring it.
        ns = runpy.run_path(str(program / "branding_301.py"))
        ns["logo_bytes"]()
        runpy.run_path(str(program / "pdf_branding_305.py"))["logo_bytes"]()
        runpy.run_path(str(program / "design_rows_306.py"))["selftest"]()
        runpy.run_path(str(program / "zvx_tables_303.py"))["selftest"]()
        if _digest(database) != before:
            raise RuntimeError("actions.sqlite3 se během instalace změnila.")
        _atomic_write(program / MARKER, VERSION.encode("utf-8"))
        if not _revision_ok(program):
            raise RuntimeError(f"Runtime TURTO {VERSION} neprošel závěrečnou kontrolou.")
    except Exception:
        for target in reversed(targets):
            data = backups[target]
            if data is None:
                target.unlink(missing_ok=True)
            else:
                _atomic_write(target, data)
        raise
    return program / "app_runtime.pyw"


def selftest() -> None:
    assert VERSION == "3.0.21" and RUNTIME_LAYOUT == "52"
    assert len(BASE_COMMIT) == 40 and len(BASE_SHA256) == 64
    assert "actions.sqlite3" not in PAYLOADS
    assert all(Path(n).name == n and len(p[0]) == 40 and len(p[2]) == 64 for n, p in PAYLOADS.items())


if __name__ == "__main__":
    selftest()
