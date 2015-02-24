# -*- Mode: python; coding: utf-8; tab-width: 4; indent-tabs-mode: nil; -*-
#
# Copyright (C) 2015 - fossfreedom
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA 02110-1301  USA.
import locale
import gettext
import os
import shutil
import webbrowser

from gi.repository import Gio
from gi.repository import GObject
from gi.repository import Gtk
from gi.repository import PeasGtk
from gi.repository import Peas
from gi.repository import RB
from gi.repository import Gdk
from gi.repository import GLib

import rb
from stars import ReactiveStar
from stars import StarSize
import coverart_rb3compat as rb3compat


class GSetting:
    '''
    This class manages the different settings that the plugin has to
    access to read or write.
    '''
    # storage for the instance reference
    __instance = None

    class __impl:
        """ Implementation of the singleton interface """
        # below public variables and methods that can be called for GSetting
        def __init__(self):
            '''
            Initializes the singleton interface, assigning all the constants
            used to access the plugin's settings.
            '''
            self.Path = self._enum(
                PLUGIN='org.gnome.rhythmbox.plugins.spectrum')


            self.PluginKey = self._enum(
                POSITION='position')

            self.setting = {}

        def get_setting(self, path):
            '''
            Return an instance of Gio.Settings pointing at the selected path.
            '''
            try:
                setting = self.setting[path]
            except:
                self.setting[path] = Gio.Settings.new(path)
                setting = self.setting[path]

            return setting

        def get_value(self, path, key):
            '''
            Return the value saved on key from the settings path.
            '''
            return self.get_setting(path)[key]

        def set_value(self, path, key, value):
            '''
            Set the passed value to key in the settings path.
            '''
            self.get_setting(path)[key] = value

        def _enum(self, **enums):
            '''
            Create an enumn.
            '''
            return type('Enum', (), enums)

    def __init__(self):
        """ Create singleton instance """
        # Check whether we already have an instance
        if GSetting.__instance is None:
            # Create and remember instance
            GSetting.__instance = GSetting.__impl()

        # Store instance reference as the only member in the handle
        self.__dict__['_GSetting__instance'] = GSetting.__instance

    def __getattr__(self, attr):
        """ Delegate access to implementation """
        return getattr(self.__instance, attr)

    def __setattr__(self, attr, value):
        """ Delegate access to implementation """
        return setattr(self.__instance, attr, value)


class Preferences(GObject.Object, PeasGtk.Configurable):
    '''
    Preferences for the Plugins. It holds the settings for
    the plugin and also is the responsible of creating the preferences dialog.
    '''
    __gtype_name__ = 'SpectrumPreferences'
    object = GObject.property(type=GObject.Object)

    def __init__(self):
        '''
        Initialises the preferences, getting an instance of the settings saved
        by Gio.
        '''
        GObject.Object.__init__(self)
        gs = GSetting()
        self.settings = gs.get_setting(gs.Path.PLUGIN)

        self._first_run = True

    def do_create_configure_widget(self):
        '''
        Creates the plugin's preferences dialog
        '''
        return self._create_display_contents(self)

    def display_preferences_dialog(self, plugin):
        print("DEBUG - display_preferences_dialog")
        if self._first_run:
            self._first_run = False

            self._dialog = Gtk.Dialog(modal=True, destroy_with_parent=True)
            self._dialog.add_button(Gtk.STOCK_OK, Gtk.ResponseType.OK)
            self._dialog.set_title(_('Spectrum Preferences'))
            content_area = self._dialog.get_content_area()
            content_area.pack_start(self._create_display_contents(plugin), True, True, 0)

            helpbutton = self._dialog.add_button(Gtk.STOCK_HELP, Gtk.ResponseType.HELP)
            helpbutton.connect('clicked', self._display_help)

        self._dialog.show_all()

        print("shown")

        while True:
            response = self._dialog.run()

            print("and run")

            if response != Gtk.ResponseType.HELP:
                break

        self._dialog.hide()

        print("DEBUG - display_preferences_dialog end")

    def _create_display_contents(self, plugin):
        print("DEBUG - create_display_contents")
        # create the ui
        self._first_run = True
        builder = Gtk.Builder()
        builder.add_from_file(rb.find_plugin_file(plugin,
                                                  'ui/spectrum_prefs.ui'))

        builder.connect_signals(self)

        gs = GSetting()
        # bind the toggles to the settings

        self.position = self.settings[gs.PluginKey.POSITION]
        self.sidebar_position_radiobutton = builder.get_object('sidebar_position_radiobutton')
        self.bottom_position_radiobutton = builder.get_object('bottom_position_radiobutton')
        
        if self.position == 1:
            self.sidebar_position_radiobutton.set_active(True)
        else:
            self.bottom_position_radiobutton.set_active(True)
        
        # return the dialog
        self._first_run = False
        print("end create dialog contents")
        return builder.get_object('main_grid')

    def on_position_radiobutton_toggled(self, button):
        if button.get_active():
            gs = GSetting()
            if button == self.sidebar_position_radiobutton:
                self.settings[gs.PluginKey.POSITION] = 1
            else:
                self.settings[gs.PluginKey.POSITION] = 2
