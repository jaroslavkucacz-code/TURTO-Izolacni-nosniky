"""Frozen Python host; application sources remain updateable beside the EXE."""
from pathlib import Path
import os
import runpy
import sys
import traceback


def main():
    root = Path(sys.executable).resolve().parent
    os.environ['TURTO_ROOT'] = str(root)
    os.environ['TURTO_PROGRAM_DIR'] = str(root / 'Program')
    sys.path[:0] = [str(root / 'Program'), str(root)]
    # A windowed executable has no console. Keep diagnostics available on disk.
    log = root / 'Logy' / 'exe.log'
    log.parent.mkdir(parents=True, exist_ok=True)
    if sys.stdout is None:
        sys.stdout = open(log, 'a', encoding='utf-8', buffering=1)
    if sys.stderr is None:
        sys.stderr = sys.stdout
    arguments = sys.argv[1:]
    worker = bool(arguments)
    if arguments and arguments[0] == '--run-script':
        arguments.pop(0)
        if not arguments:
            raise ValueError('Chybí cesta ke skriptu.')
    if arguments:
        script = Path(arguments.pop(0)).resolve()
        if script.suffix.lower() not in ('.py', '.pyw'):
            raise ValueError('Nepodporovaný příkaz TURTO Statika.')
    else:
        script = root / 'app.pyw'
    sys.argv = [str(script), *arguments]
    try:
        runpy.run_path(str(script), run_name='__main__')
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        if not worker:
            from tkinter import Tk, messagebox
            window = Tk(); window.withdraw()
            messagebox.showerror('TURTO Statika', f'Program nelze spustit. Podrobnosti: {log}', parent=window)
            window.destroy()
        raise SystemExit(2)


if __name__ == '__main__':
    main()
