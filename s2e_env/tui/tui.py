"""
Copyright (c) 2017 Cyberhaven

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""




import curses
import time


_s_screen = None

# TODO: this module requires clean up
# pylint: disable=too-many-instance-attributes
# pylint: disable=too-many-arguments
# pylint: disable=no-self-use


class Form:
    def __init__(self, parent, x, y, w=None, h=None):
        self._children = []
        self._parent = parent

        self._x = x
        self._y = y
        self._h = h
        self._w = w
        self._vcenter, self._hcenter = False, False

        self.set_size(w, h)

        ax, ay = self.get_screen_coords(0, 0)
        self._wnd = curses.newwin(self._h, self._w, ay, ax)

        if parent is not None:
            parent._children.append(self)

    @property
    def x(self):
        return self._x

    @property
    def y(self):
        return self._y

    @property
    def width(self):
        return self._w

    @width.setter
    def width(self, value):
        self._w = value

    @property
    def height(self):
        return self._h

    @height.setter
    def height(self, value):
        self._h = value

    @property
    def window(self):
        return self._wnd

    def get_screen_coords(self, x, y):
        form = self
        ax, ay = x, y
        while form is not None:
            ax, ay = ax + form.x, ay + form.y
            form = form.get_parent()
        return ax, ay

    def set_pos(self, x, y):
        self._x, self._y = x, y

    def set_centering(self, hcenter, vcenter):
        if self._parent is None:
            raise Exception('Form must have a parent')

        self._vcenter = vcenter
        self._hcenter = hcenter

    def set_size(self, w=None, h=None):
        """
        Width and Height can be set to None to expand the window
        to the size of the parent container.
        """
        if w is None or h is None:
            form = self.get_parent()
            if form is None:
                mh, mw = _s_screen.getmaxyx()
            else:
                mh, mw = form.height, form.width

        if w is None:
            w = mw
        if h is None:
            h = mh

        self._w, self._h = w, h

    def get_parent(self):
        return self._parent

    def get_draw_coords(self, ax, ay):
        x, y = self.x, self.y

        # Center the form in the parent window if needed
        if self._hcenter:
            x = (self._parent._w - self._w) // 2
        if self._vcenter:
            y = (self._parent._h - self._h) // 2

        x += ax
        y += ay

        return x, y

    def draw(self, ax, ay):
        x, y = self.get_draw_coords(ax, ay)

        # TODO: clipping
        self.do_draw(x, y)

        for child in self._children:
            child.draw(x, y)

    def do_draw(self, ax, ay):
        self._wnd.mvwin(ay, ax)
        self._wnd.resize(self._h, self._w)
        self._wnd.border()
        self._wnd.refresh()


class Label(Form):
    def __init__(self, parent, x, y, text):
        super(Label, self).__init__(parent, x, y, len(text) + 2, 1)
        self._text = ' %s' % text

    def do_draw(self, ax, ay):
        self._wnd.mvwin(ay, ax)
        self._wnd.resize(self._h, self._w)
        self._wnd.addstr(0, 0, self._text)
        self._wnd.refresh()


class Table(Form):
    def __init__(self, parent, x, y, data, legend, layout):
        self._data = data
        self._legend = legend
        self._layout = layout
        self.set_data(data, legend, layout)
        w, h = self._get_dimensions()
        super(Table, self).__init__(parent, x, y, w, h)

    def _get_dimensions(self):
        lw, dw, h = self._compute_data_size()
        w, h = self._compute_bounding_box(lw, dw, h)
        return w, h

    def _update_dimensions(self):
        w, h = self._get_dimensions()
        self.width = w
        self.height = h

    def set_data(self, data, legend, layout):
        self._data = data
        self._legend = legend
        self._layout = layout
        self._update_dimensions()

    def _compute_bounding_box(self, lw, dw, h):
        return lw + dw + 5, h

    def _compute_data_size(self):
        max_legend_width = 0
        max_data_width = 0
        max_height = len(self._layout)

        for k, v in self._data.items():
            l = self._legend[k]
            max_legend_width = max(max_legend_width, len(l))
            max_data_width = max(max_data_width, len(str(v)))

        return max_legend_width, max_data_width, max_height

    def do_draw(self, ax, ay):
        y = 0
        lw, dw, h = self._compute_data_size()
        w, h = self._compute_bounding_box(lw, dw, h)
        self._wnd.clear()
        self._wnd.resize(h, w)
        self._wnd.mvwin(ay, ax)

        # self._wnd.border()
        for k in self._layout:
            l = self._legend[k]
            if not k in self._data:
                continue
            v = self._data[k]
            self._wnd.addstr(y, 0, l + ':')
            self._wnd.addstr(y, lw + 3, str(v))
            y += 1

        self._wnd.refresh()


class Tui:
    def __init__(self):
        self._updated = True
        self._data = {}
        self._legend = {}
        self._layout = {}
        self._desktop = None
        self._stats = None
        self._title = None
        self._exitmsg = None
        self._table = None

    def _create_desktop(self):
        global _s_screen
        _s_screen = curses.initscr()
        curses.noecho()
        curses.curs_set(0)
        curses.start_color()
        self._desktop = Form(None, 0, 0)

        self._stats = Form(self._desktop, 0, 0, 70, 20)
        self._stats.set_centering(True, True)

        self._title = Label(self._stats, 0, 0, 'S2E')
        self._title.set_centering(True, False)

        self._exitmsg = Label(self._stats, 0, 17, 'Press q to exit')
        self._exitmsg.set_centering(True, False)

        self._table = Table(self._stats, 2, 2, self._data, self._legend,
                            self._layout)
        self._table.set_centering(True, True)

    def _cleanup(self):
        curses.nocbreak()
        _s_screen.keypad(0)
        curses.echo()
        curses.endwin()

    def _redraw(self):
        self._desktop.window.clear()
        self._desktop.set_size()
        self._desktop.draw(0, 0)

    def set_content(self, data, legend, layout):
        self._data = data
        self._legend = legend
        self._layout = layout
        self._updated = True
        self._table.set_data(data, legend, layout)

    def _run(self, callback):
        self._create_desktop()

        if not callback(self):
            return

        self._redraw()
        self._desktop.window.nodelay(True)

        while True:
            c = self._desktop.window.getch()
            if c == curses.ERR:
                if not callback(self):
                    return

                time.sleep(1)

            elif c == ord('q'):
                break
            elif c == curses.KEY_RESIZE:
                self._updated = True

            if self._updated:
                self._redraw()
                self._updated = False

    def run(self, callback):
        try:
            self._run(callback)
        except Exception:
            self._cleanup()
            # Print message only after screen is restored, otherwise we might
            # get unreadable garbage.
            raise
        finally:
            self._cleanup()
