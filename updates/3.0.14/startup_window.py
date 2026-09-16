"""Small native Windows loading window, independent of the application's Tk.

Its own message loop remains responsive while Python loads catalogue data.
It never creates another Tk interpreter or changes Tk's default root.
"""
import sys
import threading
import traceback

TITLE = 'TURTO Statika – Načítání'


class LoadingWindow:
    def __init__(self):
        self.text = 'Spouštím program…'
        self.hwnd = None
        self.closed = False
        self.started = threading.Event()
        self.thread = None
        self.error = None

    def start(self):
        if sys.platform == 'win32':
            self.thread = threading.Thread(target=self._run, name='TURTO startup', daemon=True)
            self.thread.start()
            self.started.wait(1)
        return self

    def message(self, text):
        self.text = str(text)
        if self.hwnd:
            self.user32.PostMessageW(self.hwnd, 0x8001, 0, 0)

    def close(self):
        self.closed = True
        if self.hwnd:
            self.user32.PostMessageW(self.hwnd, 0x0010, 0, 0)
        if self.thread and self.thread is not threading.current_thread():
            self.thread.join(1)

    def _run(self):
        try:
            self._windows_loop()
        except Exception:
            self.error = traceback.format_exc()
            print(self.error, file=sys.stderr)
        finally:
            self.hwnd = None
            self.started.set()

    def _windows_loop(self):
        import ctypes as c
        from ctypes import wintypes as w
        user = c.WinDLL('user32', use_last_error=True)
        kernel = c.WinDLL('kernel32', use_last_error=True)
        gdi = c.WinDLL('gdi32', use_last_error=True)
        self.user32 = user
        result_type = c.c_ssize_t
        proc_type = c.WINFUNCTYPE(result_type, w.HWND, w.UINT, w.WPARAM, w.LPARAM)

        class WindowClass(c.Structure):
            _fields_ = [('style', w.UINT), ('proc', proc_type), ('class_extra', c.c_int),
                        ('window_extra', c.c_int), ('instance', w.HINSTANCE), ('icon', w.HICON),
                        ('cursor', w.HANDLE), ('brush', w.HBRUSH), ('menu', w.LPCWSTR), ('name', w.LPCWSTR)]

        class CommonControls(c.Structure):
            _fields_ = [('size', w.DWORD), ('classes', w.DWORD)]

        def api(dll, name, restype, *args):
            fn = getattr(dll, name); fn.restype = restype; fn.argtypes = list(args)
            return fn

        api(kernel, 'GetModuleHandleW', w.HINSTANCE, w.LPCWSTR)
        api(user, 'RegisterClassW', w.ATOM, c.POINTER(WindowClass))
        api(user, 'UnregisterClassW', w.BOOL, w.LPCWSTR, w.HINSTANCE)
        api(user, 'CreateWindowExW', w.HWND, w.DWORD, w.LPCWSTR, w.LPCWSTR, w.DWORD,
            c.c_int, c.c_int, c.c_int, c.c_int, w.HWND, w.HMENU, w.HINSTANCE, w.LPVOID)
        api(user, 'DefWindowProcW', result_type, w.HWND, w.UINT, w.WPARAM, w.LPARAM)
        api(user, 'PostMessageW', w.BOOL, w.HWND, w.UINT, w.WPARAM, w.LPARAM)
        api(user, 'SendMessageW', result_type, w.HWND, w.UINT, w.WPARAM, w.LPARAM)
        api(user, 'DestroyWindow', w.BOOL, w.HWND)
        api(user, 'ShowWindow', w.BOOL, w.HWND, c.c_int)
        api(user, 'UpdateWindow', w.BOOL, w.HWND)
        api(user, 'SetWindowTextW', w.BOOL, w.HWND, w.LPCWSTR)
        api(user, 'GetMessageW', w.BOOL, c.POINTER(w.MSG), w.HWND, w.UINT, w.UINT)
        api(user, 'TranslateMessage', w.BOOL, c.POINTER(w.MSG))
        api(user, 'DispatchMessageW', result_type, c.POINTER(w.MSG))
        api(gdi, 'CreateFontW', w.HANDLE, *([c.c_int]*5), *([w.DWORD]*8), w.LPCWSTR)
        api(gdi, 'DeleteObject', w.BOOL, w.HANDLE)

        instance = kernel.GetModuleHandleW(None)
        stage = None

        @proc_type
        def procedure(hwnd, message, wp, lp):
            if message == 0x8001 and stage:
                user.SetWindowTextW(stage, self.text)
                return 0
            if message == 0x0010:
                user.DestroyWindow(hwnd)
                return 0
            if message == 0x0002:
                user.PostQuitMessage(0)
                return 0
            return user.DefWindowProcW(hwnd, message, wp, lp)

        name = 'TurtoLoading_' + str(id(self))
        wc = WindowClass(0, procedure, 0, 0, instance, None, None, 6, None, name)
        if not user.RegisterClassW(c.byref(wc)):
            raise c.WinError(c.get_last_error())
        fonts = []
        try:
            scale = 1.0
            try:
                # Do this before the first window. The main application requests
                # the same process DPI awareness later (an idempotent request).
                c.windll.shcore.SetProcessDpiAwareness(1)
                scale = user.GetDpiForSystem()/96
            except (AttributeError, OSError):
                pass
            px = lambda value: round(value*scale)
            width, height = px(480), px(186)
            x = max(0, (user.GetSystemMetrics(0)-width)//2)
            y = max(0, (user.GetSystemMetrics(1)-height)//2)
            hwnd = user.CreateWindowExW(0x00000080, name, TITLE, 0x80800000,
                                        x, y, width, height, None, None, instance, None)
            if not hwnd:
                raise c.WinError(c.get_last_error())
            self.hwnd = hwnd

            def label(text, y, size, weight=400):
                child = user.CreateWindowExW(0, 'STATIC', text, 0x50000000,
                                              px(26), px(y), px(426), px(36), hwnd, None, instance, None)
                font = gdi.CreateFontW(-px(size), 0, 0, 0, weight, 0, 0, 0, 1, 0, 0, 5, 0, 'Calibri')
                fonts.append(font)
                user.SendMessageW(child, 0x0030, font, 1)
                return child

            label('TURTO Statika', 22, 29, 700)
            stage = label(self.text, 73, 17)
            cc = CommonControls(c.sizeof(CommonControls), 0x20)
            c.windll.comctl32.InitCommonControlsEx(c.byref(cc))
            bar = user.CreateWindowExW(0, 'msctls_progress32', '', 0x50000008,
                                      px(26), px(126), px(426), px(12), hwnd, None, instance, None)
            if bar:
                user.SendMessageW(bar, 0x040A, 1, 35)  # PBM_SETMARQUEE
            user.ShowWindow(hwnd, 4)  # SW_SHOWNOACTIVATE: leave user's focus alone.
            user.UpdateWindow(hwnd)
            self.started.set()
            if self.closed:
                user.PostMessageW(hwnd, 0x0010, 0, 0)
            message = w.MSG()
            while user.GetMessageW(c.byref(message), None, 0, 0) > 0:
                user.TranslateMessage(c.byref(message))
                user.DispatchMessageW(c.byref(message))
        finally:
            if self.hwnd:
                user.DestroyWindow(self.hwnd)
            for font in fonts:
                if font:
                    gdi.DeleteObject(font)
            user.UnregisterClassW(name, instance)
