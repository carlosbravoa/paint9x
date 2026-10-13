"""Gtk.Application entry point."""

import os
import sys
import time

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, Gio, GLib, Gtk  # noqa: E402

from . import APP_ID  # noqa: E402

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


def load_css():
    screen = Gdk.Screen.get_default()
    provider = Gtk.CssProvider()
    provider.load_from_path(os.path.join(DATA_DIR, "win98.css"))
    Gtk.StyleContext.add_provider_for_screen(screen, provider, Gtk.STYLE_PROVIDER_PRIORITY_USER + 1)
    settings = Gtk.Settings.get_default()
    # Classic behaviour: no animations, mnemonics always underlined,
    # clicking the trough pages instead of jumping.
    for prop, value in (("gtk-enable-animations", False),
                        ("gtk-auto-mnemonics", False),
                        ("gtk-primary-button-warps-slider", False),
                        ("gtk-menu-bar-popup-delay", 0)):
        try:
            settings.set_property(prop, value)
        except TypeError:
            pass


def migrate_old_dirs():
    """Paint9X used to be called Paint98: carry its settings, recovery
    copies and stickers over to the new folder names."""
    for base in (GLib.get_user_config_dir(), GLib.get_user_data_dir()):
        old, new = os.path.join(base, "paint98"), os.path.join(base, "paint9x")
        if os.path.isdir(old) and not os.path.exists(new):
            try:
                os.rename(old, new)
            except OSError:
                pass


def open_store_page(win):
    """Show Paint9X in the App Center, or on the web if that can't be opened."""
    for uri in ("snap://paint9x", "https://snapcraft.io/paint9x"):
        try:
            Gtk.show_uri_on_window(win, uri, Gtk.get_current_event_time())
            return True
        except GLib.Error:
            pass
    return False


class PaintApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID,
                         flags=Gio.ApplicationFlags.HANDLES_OPEN | Gio.ApplicationFlags.NON_UNIQUE)
        GLib.set_application_name("Paint9X")

    def do_startup(self):
        Gtk.Application.do_startup(self)
        load_css()

    _checked_recovery = False

    def new_window(self, path=None):
        from .window import MainWindow
        win = MainWindow(self, path)
        win.show_all()
        win.present()
        if not self._checked_recovery:
            self._checked_recovery = True
            GLib.idle_add(self.offer_recovery, win)
        return win

    def offer_recovery(self, win):
        """After a crash, offer the pictures that were autosaved."""
        from . import autosave
        from .win98 import message_box
        from .window import display_path
        for sid, info, png in autosave.find_orphans():
            name = info.get("filename")
            name = display_path(os.path.basename(name)) if isinstance(name, str) else "untitled"
            when = info.get("time")
            when = time.strftime("%d/%m/%Y %H:%M", time.localtime(when)) \
                if isinstance(when, (int, float)) else "an earlier session"
            res = message_box(win, "Paint9X",
                              "Paint9X found an unsaved picture (%s) from %s.\n"
                              "It was not saved before Paint9X closed.\n\n"
                              "Do you want to recover it?" % (name, when),
                              ("Yes", "No"), icon="info")
            if res == 0:
                doc = win.doc
                untouched = not doc.modified and doc.filename is None and not doc.undo_stack
                target = win if untouched else self.new_window()
                target.recover(png, info)
            autosave.discard(sid)
        self.offer_new_snap(win)
        return False

    def offer_new_snap(self, win):
        """The "paint98" snap gets no more updates: point its users to "paint9x"."""
        if os.environ.get("SNAP_NAME") != "paint98" or win.settings.get("hide_move_notice"):
            return
        from .win98 import message_box
        res = message_box(win, "Paint9X",
                          "Paint98 is now called Paint9X, and this copy will not get any "
                          "more updates.\n\n"
                          "To keep getting new features and fixes, install Paint9X from the "
                          "App Center, or with this command:\n\n"
                          "    sudo snap install paint9x\n\n"
                          "Then you can remove this copy with \"sudo snap remove paint98\". "
                          "Your pictures stay where they are.",
                          ("Get Paint9X", "Later", "Don't Ask Again"), icon="info")
        if res == 0:
            open_store_page(win)
        elif res == 2:
            win.settings["hide_move_notice"] = True
            win.save_settings()

    def do_activate(self):
        self.new_window()

    def do_open(self, files, n_files, hint):
        for f in files:
            self.new_window(f.get_path())


def main(argv=None):
    migrate_old_dirs()
    app = PaintApp()
    return app.run(argv if argv is not None else sys.argv)
