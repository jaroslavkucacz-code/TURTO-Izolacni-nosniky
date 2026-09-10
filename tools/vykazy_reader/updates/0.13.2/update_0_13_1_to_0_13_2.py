from __future__ import annotations

import base64
import hashlib
import os
import shutil
import sys
import zlib
from datetime import datetime
from pathlib import Path

FROM_VERSION = "0.13.1"
TO_VERSION = "0.13.2"
PATCHES = [{'path': 'app.py', 'old_sha256': '4d45a36630c76845672c3ebff4e5f630bdb5eb31dca3b1fac6d02740e5800000', 'new_sha256': 'aac20265f14f42a9ed8ae8b130960e399ad7a9be15c1a9964cff3c71519b3e70', 'ops': [{'i1': 17, 'i2': 17, 'old_sha256': 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855', 'data': 'eNrLzC3ILypRKC3KyclM0kstKsov4spEEStKLSxNLS7hAgBh8RAu'}, {'i1': 25, 'i2': 26, 'old_sha256': 'c1ae0f341222d7c70a0e4698139cacebcc1ea4f9fd4f232776a125ed06e606e0', 'data': 'eNo1jstugzAURPd8RcQeu212kbpAwpEsERvxSJbWrXGLA/hGtkkFX98kUtczc87kVaXOrG64FLvPXfpG3vfkI00uXBTy0qj8EXcNq9VJFqxUvHiW2q5uJTmvI2wr33AC7aweKn8flzSRouSCqa4q8papUy74kTWt6uryOR1ivIUDpR5+yY+Nw/K1BOM1umhcJBpnegWPYYIHS4PeMo29oS9h9q/KHAZnx5XOYB2NiFOg99cZ5Q30xtPl1kM0agZnv02I5BrQpckfnd5QeQ=='}, {'i1': 62, 'i2': 62, 'old_sha256': 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855', 'data': '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'}, {'i1': 109, 'i2': 110, 'old_sha256': '5e7bcd36ef53b44523e65e98d1944993e0ff1746f5536c1a511746f3e01e756f', 'data': 'eNoDAAAAAAE='}, {'i1': 6468, 'i2': 6468, 'old_sha256': 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855', 'data': 'eNpTUICA4tScNL3SgpTEktT4zLz4gqL89KLU4mIFWwW3xJziVC4A8vsM2A=='}, {'i1': 6477, 'i2': 6477, 'old_sha256': 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855', 'data': 'eNrdV91u2zYUvs9TcLqphBpqr40JQ7p5QFYgMdqsBZoEAi1RNhOZ1EjKsRMY6AvsAYZeeRcDdpEX2EVvnLxIn2SH1I9FWfaaFrupECA2RZ6/7zvfoQ8QPDFJUBhNSHQVcpZSRsI8i7EiriRp4vUPUPnQBOkVv3gbUhZmgo8FkXKzRz+CqFywemnHGRSgU5GTepsSC9tM89xIMV8qHdOZE1OJRymJnQuv3k/mEckUGph/lDPbUoaltMPRtnIZzrDwJVGu85IzJXiaX1JUlADhK5XjlN7giHx6/5fjHdQGdLmuubgiwvVsP1sp6GeKGU2IVJBvmHIcl8UNq3XX2zqSwntzQCrhVvv8sQ50RoSE/BwPcYHsV8Wp0NrhOB7kKmjW4QXgZFyVzrbjNkhiKgl6g9OcDITgwnVOiurUSTHCRxJP8kuC7n9f38mUIwjghvjOtkNTeZwoKNzzHvidjmLcL1Zt4oV4hmmqQa6z75VxerbZNu4IS73W/yzfiAR6b2cECQRAYpd4DeDVRBAcUzb2T80nV2EBlQ8KMvRQjMmUs0CzWlcdC43tQd1hnQ60754JGb3AktSJNJi1u39+xqn8ggb67n/sINxonPUdbAWGZDzGD38AoE1STCEFPCYjPvflhF9fY8Ggsq5zuOk7p4eSinAbq9Q2ytHNVeGaz7Dqn7Nzdgu5LOFwhgVhKjAqthOHDdUKKCrC9VFMo5p2fd2KthRWjRaqPIPTJT3R90H7zeFwGL4ZvHp9dHLs7QZoH7I7teVRCP83yltI70I7cYY8f/i4vputV6oAZ71KGQCum5+i2W0j6WVbC1rQU5bwbdwf56AFdsc0qtdA84gusS2eZrXQzLOLJsxUUgbZs4i4Zk+vxYTaZKjIXGu2+bIluiTttJVS4MweY845c/xLThmU/NP7P9GtngjzWtOXDkog4jmirMxLz2hrSzMESfa5cup3v+VQF62mAQDxC0Exl0Bltl4V2g7VL9i+RC5bGFAsODxfd6FzYA+a0pMdQe3padCM5qlOvGmiuc95rdarCeO5QhgxbEpqmh9lPIfobqb3Hxj8rf9GpqPwlM/gs+T5iIvFD+24mnTE8mpBJOPutuxoVlZR2Gz7Rnq62YFotAAl53HKHz4ShtsN3G6pbok4MsB0XqnohkJfd7kqlbaHoglmYxLrSxbOsnRRqXx9y4LVUHAOI3mj8V91RQEvFAZ4O4Jv5oJSJViMxTJNMwfrXPtGv85g6eIL7ivdrGmycHZbul0iuF9uWn29Ak6iYdHc+joA9nU2cAvdc8Uwc8aquz10rFc7AzGdsf5HZvcfHlYgM+2wbN0qTL0rFYn30e2THnpSKHpFmKU+0kimkNRmSr3WXazWns0Lzy5rWB4PDaOq33NNsDs3tPRM9wvAtmmd3XdN0FIufYanBAUg0Uw5CLMYucbEM9Ds4a+vT49OwxeDd+HJy+NDfzaCceuTORBItlvdpJGPgDkRQOgPeUYYKOC1jGCkKTikxViPuf3WL4Co13FQbWx3ZvqZMfsjrB4bajSNIUTnWdQdaGGyHR98ha7VKpGkeCwDaF2s4OXGPpj88dXg8HQQHp+Eb4+Ofzp5Cw6eb2XWHvTdUcqF1LWMcqXnih0oYO5ni301TCjDadr1kyMGagm+ALr8C32ND04='}, {'i1': 6553, 'i2': 6553, 'old_sha256': 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855', 'data': 'eNp1Uk2L2zAQve+vGLQXCYw3LksPLeqltFBYSNnd9lKKmdjjSPhDQlKI019fyQ6Jt07nIAlJ8+bNmwcwx87hUIOE0OZfHfbEVUdNyGC3l566Jv+8fdo+v/xiirAmx36LO1hm5harluNQKeMkO7IMGt11ko3s+lFXZigtBhXLoLWlMyZwAQ/A0HsKnqXj64/n123589Tin1Nuhz27pjdXhJxG7YPn4sPlOUVwp7cXKWbGZcqd+/uuTDDfetwTjyRJ+uD4BVmIFcA9vJiDqwi0h2Lz7hHs+BH8Yeextx1BMIBQOe1tBp3eq3CktJ7rQo+uzVeYDVbBuMinx5EXGeghcGcOQ83TxYJyftR1UFxkyz5yNZXgIqn3+F7cIB3VOtf4BMValLUwS/hLc3zGyM5Y6zKTN8pFbumoeYu2yokjeMIddfwmq8lOUZA0H7mA+b8V40stN9ntHqNO01CC0lU7kPe3forZvl7XJFnyffSvxXqUfJNBUfwjL40V2QBfpk2bYa2ujYa++wsdveyx'}, {'i1': 6554, 'i2': 6555, 'old_sha256': 'e69de242a51fb700c7a67995ab43b6e43700144a6c93f2d2dbab7ecd0eee20d7', 'data': 'eNpTUECApKLEvBQdLgAe2AO+'}, {'i1': 6558, 'i2': 6559, 'old_sha256': '93469e060351bf8e461c193ffe571b41703c392995876cd35c1edfb730614f9b', 'data': 'eNpTUIAATb2CxORsjeLMlFRbpZzUtBIlHYXEvOSM/CJbpXIlTS4Az0wK4g=='}, {'i1': 6618, 'i2': 6618, 'old_sha256': 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855', 'data': 'eNptjsEKwyAQRO/5iiWnCEF668lD+weF3mWjGyqaVeoKSb++oV47x4F5bwB6KqVVt+JRyC7CYEAk6nsTyTwFLk1sJZfZ4/uYQWgXM96iNEzhg47GGaocicz4aIFEP/vyrF3eNmRvfgLrXuSizZwCk+06NcD/D7qgi1MN/qQmWuWEFfS7ma4zXJQavoYfPsM='}, {'i1': 8300, 'i2': 8300, 'old_sha256': 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855', 'data': 'eNpTUFBQKE4tiS/PzEvJLy+OTywoiC8tTi2Kz81PSc2Jz0zR0OQCAO1bDOw='}]}, {'path': 'README.txt', 'old_sha256': 'bf5c139764a21f351737a6bee492e88d5d6df17b2f226982c751874e4bcfbbcd', 'new_sha256': 'df2db21de07a7f38cf9757f1822661c606785e7462972ed2e2d69bd95e4a6fc5', 'ops': [{'i1': 1, 'i2': 2, 'old_sha256': 'fa86bd6adf4caaaa97fafef0733e1304df2b0a1a1b2344bbbd262905f90c07a3', 'data': 'eNoLSy2qSlUw0DM01jPiAgAcewNZ'}, {'i1': 9, 'i2': 9, 'old_sha256': 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855', 'data': 'eNqtUU1u00AU3ucU375NBEWwYWXRoFoNSdQmQepubI/qicfzLHs8yF71AlmxCkUVWbKIOEG7sX2RnoTnpCAOgPUWT5rvz98bDKazVfsNqzHP1Y2PV6PXb0ZneL77Cv9yNvXAczHxVtNmg4nf/Vgw+ASz6cSfjuFdLpbexL/xPowHw//0DYb4rExEXwp4WbYsZP6JIqn9cxQSRhRWuHItsZbdzrb3yLqtjOAq64g30+xTxFo4XmICJUacwoqke5I9fbG8WswGgErICGRUdk/N3jU7KFb+w0uRCSN1+TeGgIOn7clCBEibfWEJt9LIXIVJ8/OgVWFe2ZhMOeL011auTa95MOGopmJVOBUpK3X/woGYyMnZjFg8prxH9P6q3YQSWU63uUhLOBlpFmh2tTtoz7utCipNsFq0m2ZvE+JTPXiJLYVWtQjl8933EeZHPjiBzUn3fRUiJe7OmuYRZLQyEolgYY1V85iIuvsFwc0wJO7h3E0tUaftveHp0x4lyfFeUBlQXr1HJKwIOJzkjkQexsphfv4RawYgjPNmdyT3yf+JCHLtfbftba4vvOHZ23enL2c8+DH35ZzcSc0JKS5ZnxGKRaugP3pO3IwE/5sORJiMBr8ByhAOTw=='}]}]

def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def apply_line_patch(data: bytes, spec: dict) -> bytes:
    lines = data.decode("utf-8").splitlines(keepends=True)
    for op in reversed(spec["ops"]):
        old_segment = "".join(lines[op["i1"]:op["i2"]]).encode("utf-8")
        if sha(old_segment) != op["old_sha256"]:
            raise RuntimeError(f"Neočekávaný obsah při aktualizaci {spec['path']}.")
        replacement = zlib.decompress(base64.b64decode(op["data"])).decode("utf-8").splitlines(keepends=True)
        lines[op["i1"]:op["i2"]] = replacement
    return "".join(lines).encode("utf-8")

def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    app = root / "app.py"
    if not app.exists():
        raise RuntimeError("Ve zvolené složce nebyl nalezen app.py.")
    version_file = root / "VERSION.txt"
    current = version_file.read_text(encoding="utf-8-sig", errors="replace").strip() if version_file.exists() else ""
    if current == TO_VERSION:
        return 0
    if current and current != FROM_VERSION:
        raise RuntimeError(f"Tento krok očekává v{FROM_VERSION}, nalezena v{current}.")

    targets = [root / spec["path"] for spec in PATCHES] + [version_file]
    backup_root = root / ".update_backup" / (datetime.now().strftime("%Y%m%d_%H%M%S_%f") + "_patch_0132")
    backups = []
    try:
        for target in targets:
            backup = None
            if target.exists():
                backup = backup_root / target.relative_to(root)
                backup.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, backup)
            backups.append((target, backup))

        for spec in PATCHES:
            target = root / spec["path"]
            old = target.read_bytes()
            if sha(old) == spec["new_sha256"]:
                continue
            if sha(old) != spec["old_sha256"]:
                raise RuntimeError(f"Soubor {spec['path']} neodpovídá v{FROM_VERSION}; aktualizace jej z bezpečnostních důvodů nepřepíše.")
            new = apply_line_patch(old, spec)
            if sha(new) != spec["new_sha256"]:
                raise RuntimeError(f"Kontrola výsledku selhala: {spec['path']}")
            temp = target.with_name(target.name + ".patch_tmp")
            temp.write_bytes(new)
            os.replace(temp, target)

        tempv = version_file.with_name(version_file.name + ".patch_tmp")
        tempv.write_text(TO_VERSION + "\n", encoding="utf-8")
        os.replace(tempv, version_file)
        return 0
    except Exception:
        for target, backup in reversed(backups):
            try:
                if backup is not None and backup.exists():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(backup, target)
                elif backup is None and target.exists():
                    target.unlink()
            except Exception:
                pass
        raise

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
