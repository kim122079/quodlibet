# -*- coding: utf-8 -*-
# Copyright 2004-2005 Joe Wreschnig, Michael Urman, Iñigo Serna
#           2011-2014 Nick Boultbee
#           2014 Christoph Reiter
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 as
# published by the Free Software Foundation

import os

from gi.repository import Gtk, Gdk, Pango

from quodlibet import qltk
from quodlibet.qltk.songsmenu import SongsMenu
from quodlibet.qltk.x import SeparatorMenuItem, Align
from quodlibet.util import connect_destroy

from quodlibet.pattern import XMLFromMarkupPattern
from quodlibet.qltk.textedit import PatternEdit


class SongInfo(Gtk.EventBox):
    """A widget for showing information about the currently playing song.

    Provides a way to change the display pattern for formatting the
    song information and a song context menu.
    """

    _pattern = (u"""\
[span weight='bold' size='large']<title>[/span]\
<~length| (<~length>)><version|
[small][b]<version>[/b][/small]><~people|
%(people)s><album|
[b]<album>[/b]<discnumber| - %(disc)s>\
<discsubtitle| - [b]<discsubtitle>[/b]><tracknumber| - %(track)s>>"""
        % {
        # Translators: As in "by Artist Name"
        "people": _("by %s") % "<~people>",
        "disc": _("Disc %s") % "<discnumber>",
        "track": _("Track %s") % "<tracknumber>"
        })

    _not_playing = "<span size='xx-large'>%s</span>" % _("Not playing")

    def __init__(self, library, player, pattern_filename):
        super(SongInfo, self).__init__()
        self._pattern_filename = pattern_filename
        self.set_visible_window(False)
        align = Align(halign=Gtk.Align.START, valign=Gtk.Align.START)
        label = Gtk.Label()
        label.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
        label.set_selectable(True)
        align.add(label)
        label.set_alignment(0.0, 0.0)
        self._label = label
        connect_destroy(library, 'changed', self._on_library_changed, player)
        connect_destroy(player, 'song-started', self._on_song_started)

        label.connect('populate-popup', self._on_label_popup, player, library)
        self.connect('button-press-event', self._on_button_press_event,
                     player, library)

        try:
            with open(self._pattern_filename, "rb") as h:
                self._pattern = h.read().strip().decode("utf-8")
        except (EnvironmentError, UnicodeDecodeError):
            pass

        self._compiled = XMLFromMarkupPattern(self._pattern)
        align.show_all()
        self.add(align)

    def _on_button_press_event(self, widget, event, player, library):
        if event.button == Gdk.BUTTON_SECONDARY:
            menu = self._get_menu(player, library)
            menu.attach_to_widget(widget, None)
            menu.popup(None, None, None, None, event.button, event.time)
            return True
        return False

    def _on_label_popup(self, label, menu, player, library):
        song_menu = self._get_menu(player, library)

        has_selection = label.get_selection_bounds()[0]

        if not has_selection:
            for child in menu.get_children():
                child.destroy()
            for item in song_menu:
                song_menu.remove(item)
                menu.append(item)
        else:
            sub = Gtk.MenuItem.new_with_mnemonic(("Current _Song"))
            sub.set_submenu(song_menu)
            sub.set_sensitive(player.song is not None)
            sub.show_all()
            sep = SeparatorMenuItem()
            sep.show()
            menu.append(sep)
            menu.append(sub)

    def _get_menu(self, player, library):
        item = qltk.MenuItem(_(u"_Edit Display…"), Gtk.STOCK_EDIT)
        item.connect('activate', self._on_edit_display, player)

        songs = [player.song] if player.song else []
        song_menu = SongsMenu(library, songs, remove=False,
                              accels=False, items=[[item]])

        song_menu.show_all()
        return song_menu

    def _on_edit_display(self, menu_item, player):
        editor = PatternEdit(self, SongInfo._pattern)
        editor.text = self._pattern
        editor.apply.connect('clicked', self._on_set_pattern, editor, player)
        editor.show()

    def _on_set_pattern(self, button, edit, player):
        self._pattern = edit.text.rstrip()
        if self._pattern == SongInfo._pattern:
            try:
                os.unlink(self._pattern_filename)
            except OSError:
                pass
        else:
            try:
                with open(self._pattern_filename, "wb") as h:
                    h.write(self._pattern.encode("utf-8") + "\n")
            except EnvironmentError:
                pass
        self._compiled = XMLFromMarkupPattern(self._pattern)
        self._update_info(player)

    def _on_library_changed(self, library, songs, player):
        if player.info in songs:
            self._update_info(player)

    def _on_song_started(self, player, song):
        self._update_info(player)

    def _update_info(self, player, _last={}):
        text = (self._not_playing if player.info is None
                else self._compiled % player.info)

        # some radio streams update way too often and updating the label
        # destroys the text selection
        if text not in _last:
            self._label.set_markup(text)
            _last.clear()
            _last[text] = True
