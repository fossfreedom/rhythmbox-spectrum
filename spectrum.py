# -*- Mode: python; coding: utf-8; tab-width: 4; indent-tabs-mode: nil; -*-
#
# Copyright (C) 2014 - fossfreedom
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3, or (at your option)
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

# define plugin

from gi.repository import Gtk
from gi.repository import Gst
from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Peas
from gi.repository import Gdk
from gi.repository import RB
from spectrum_rb3compat import ActionGroup
from spectrum_rb3compat import ApplicationShell
import cairo

from collections import namedtuple
Rect = namedtuple('Rectangle', 'x y width height')

LINEAR_COLORS = [
                 (1.0, 0.9176470588235294, 0.5764705882352941),
                 (1.0, 0.8392156862745098, 0.19215686274509805)]

LINEAR_POS = [0.3, 0.8]

view_menu_ui = """
<ui>
    <menubar name="MenuBar">
        <menu name="ViewMenu" action="View">
            <menuitem name="Spectrum" action="ToggleSpectrum" />
        </menu>
    </menubar>
</ui>
"""

class SpectrumPlugin(GObject.Object, Peas.Activatable):
    '''
    Main class of the plugin. Manages the activation and deactivation of the
    plugin.
    '''
    __gtype_name = 'SpectrumPlugin'
    object = GObject.property(type=GObject.Object)

    def __init__(self):
        '''
        Initialises the plugin object.
        '''
        GObject.Object.__init__(self)

    def do_activate(self):
        '''
        Called by Rhythmbox when the plugin is activated. It creates the
        plugin's source and connects signals to manage the plugin's
        preferences.
        '''

        self.shell = self.object
        self.db = self.shell.props.db
        self.appshell = ApplicationShell(self.shell)
        
        self.toggle_action_group = ActionGroup(self.shell, 'SpectrumPluginActions')
        self.toggle_action_group.add_action(func=self.toggle_visibility,
            action_name='ToggleSpectrum', label=_("Spectrum"), action_state=ActionGroup.TOGGLE,
            action_type='app', accel="<Ctrl>s", tooltip=_("Display spectrum for the current playing song"))
        self.appshell.insert_action_group(self.toggle_action_group)
        self.appshell.add_app_menuitems(view_menu_ui, 'SpectrumPluginActions', 'view')
        self.box = None
        
        
    def do_deactivate(self):
        '''
        Called by Rhythmbox when the plugin is deactivated. It makes sure to
        free all the resources used by the plugin.
        '''
        self.appshell.cleanup()
        if self.box:
            self.box.hide()
            self.shell.remove_widget(self.box,
                                            RB.ShellUILocation.MAIN_BOTTOM)
        del self.shell
        del self.db
        
    def toggle_visibility(self, action, param=None, data=None):
        action = self.toggle_action_group.get_action('ToggleSpectrum')
        
        if action.get_active():
            win = SpectrumPlayer()
            win.show_all()
            win.initialise(self.shell)
            self.box = Gtk.Box()
            self.box.add(win)
            self.shell.add_widget(self.box,
                                 RB.ShellUILocation.MAIN_BOTTOM, expand=True, fill=True)
            self.box.show_all()
        else:
            self.box.hide()
            self.shell.remove_widget(self.box,
                                            RB.ShellUILocation.MAIN_BOTTOM)
            self.box = None

class SpectrumPlayer(Gtk.DrawingArea):
    __gsignals__ = {
        "spectrum-data-found" : (GObject.SIGNAL_RUN_LAST,
                GObject.TYPE_NONE,
                (GObject.TYPE_PYOBJECT,))
                    }
    def __init__(self):
        super(SpectrumPlayer, self).__init__()
        
        # init
        self.spect_height = 100
        self.spect_bands = 64
        self.spect_atom = 64.0
        self.height_scale = 1.0
        self.band_width = 6
        self.band_interval = 3
        self.spect_data = None
        
        self.spectrum = Gst.ElementFactory.make("spectrum", "spectrum")
        self.spectrum.set_property("bands", self.spect_bands)
        self.spectrum.set_property("threshold", -80)
        self.spectrum.set_property("post-messages", True)
        self.spectrum.set_property('message-magnitude', True)
        
        self.connect("spectrum-data-found", self.on_event_load_spect)
        
        self.set_size_request(self.adjust_width, self.spect_height)
        self.connect("draw", self.draw_cb)
        self.connect("configure-event", self.on_configure_event)
        
        self.drag_flag = False
        self.mouse_x = self.mouse_y = 0
        self.old_x = self.old_y = 0
        
    def initialise(self, shell):
        player = shell.props.shell_player.props.player
        player.add_filter(self.spectrum)
        
        if not player.props.playbin:
            player.connect('notify', self.on_player_notify)     
        else:
            bus = player.props.playbin.get_bus()
            bus.connect('message', self.message_handler)
        
    def message_handler(self, bus, message):
        if message.type == Gst.MessageType.ELEMENT:
            s = message.get_structure()
            name = s.get_name()
            
            if name == "spectrum":
                waittime = 0
                if s.has_field("running_time") and s.has_field("duration"):
                    timestamp = s.get_value("running_time")
                    duration = s.get_value("duration")
                    waittime = timestamp + duration / 2
                elif s.has_field("endtime"):
                    waittime = s.get_value("endtime")
                    
                if waittime:
                    # workaround bug where the magnitude field is a type not understood in python
                    fullstr = s.to_string()
                    magstr = fullstr[fullstr.find('{') + 1 : fullstr.rfind('}') - 1]
                    magnitude_list = [float(x) for x in magstr.split(',')]
                    self.emit("spectrum-data-found", magnitude_list)
                
        return True
                    
    def on_player_notify(self, widget, spec):
        if spec.name == "playbin":
            playbin = widget.get_property('playbin')
            bus = playbin.get_bus()
            bus.connect('message', self.message_handler)
                
    def on_player_tee_removed(self, pbin, tee, element):
        if element != self.spectrum:
            return
        self.spectrum.set_state(gst.STATE_NULL)
        
    @property
    def adjust_width(self):
        return (self.band_width + self.band_interval) * self.spect_bands
        
    #def on_expose_event(self, widget, event):
    def draw_cb(self, widget, cr):
        rect = widget.get_allocation()
        
        cr.set_operator(cairo.OPERATOR_SOURCE)
        #cr.set_source_rgba(1.0, 1.0, 1.0, 0.0)
        context = self.get_toplevel().get_style_context()
        bg_colour = context.get_color(Gtk.StateFlags.NORMAL)
        Gdk.cairo_set_source_rgba(cr, bg_colour)
        cr.rectangle(0, 0, rect.width, rect.height)
        cr.fill()
        
        cr.set_operator(cairo.OPERATOR_OVER)
        self.draw_spectrum(cr)
        return True
        
        
    def delayed_idle_spectrum_update(self, spect):
        self.spect_data = spect
        self.queue_draw()
        
        return False
    
    def on_event_load_spect(self, obj, magnitude_list):
        spect = [i * self.height_scale for i in magnitude_list]
        GLib.idle_add(self.delayed_idle_spectrum_update, spect)
    
    def on_configure_event(self, widget, event):
        self.spect_height = event.height
        self.height_scale = event.height / self.spect_atom
        self.spect_bands = event.width / (self.band_width + self.band_interval)
        
        self.spectrum.set_property("bands", int(self.spect_bands))
        return False
    
    def draw_spectrum(self, cr):
        start = 5
        data = self.spect_data
        if data:
            for i in range(int(self.spect_bands)):
                print (i)
                cr.push_group()
                cr.set_source_rgb(1, 1, 1)
                rect = Rect(start, -data[i], self.band_width, self.spect_height + data[i])

                
                pattern = cairo.LinearGradient(rect.x, rect.y, rect.x, rect.y + rect.height)
                for i, each_linear in enumerate(LINEAR_COLORS):
                    pattern.add_color_stop_rgb(LINEAR_POS[i],
                                               each_linear[0],
                                               each_linear[1],
                                               each_linear[2])
            
                    cr.set_source(pattern)
                
                cr.rectangle(*rect)
                cr.fill()
                cr.pop_group_to_source()
                cr.paint_with_alpha(0.5)
                start += self.band_width + self.band_interval
                
