import typing
import os
import sys
import subprocess
import json
import inspect

import wx
import wx.lib.filebrowsebutton
import wx.lib.scrolledpanel

from blend_converter import utils
from blend_converter import common
from blend_converter import settings_base
from blend_converter.gui import program_ui
from blend_converter.gui import wxp_utils


ROOT = os.path.dirname(os.path.realpath(__file__))


WX_GREEN_COLOR = wx.Colour(200, 255, 200)
WX_RED_COLOR = wx.Colour(255, 200, 200)
WX_WHITE_COLOR = wx.Colour(255, 255, 255)


if typing.TYPE_CHECKING:
    import dataclasses
else:
    class dataclasses:
        dataclass = lambda x: x


def start_launcher(programs):

    app = wx.App()
    frame = Launcher(programs)
    frame.Show()
    app.MainLoop()


class File_Drop_Target(wx.FileDropTarget):


    def __init__(self, ctrl: wx.FilePickerCtrl):
        super().__init__()
        self.ctrl = ctrl


    def OnDropFiles(self, x, y, filenames):

        path: str = filenames[0]

        if os.name == 'nt' and path.lower().endswith('.lnk'):

            from blend_converter.windows import win_utils

            path = win_utils.get_shortcut_target(path)
            if not path:
                return False

        if os.path.basename(path).lower() == 'blender-launcher.exe':
            path = os.path.join(os.path.dirname(path), 'blender.exe')

        self.ctrl.SetValue(path)

        return True


class FolderBrowseButtonWithHistory(wx.lib.filebrowsebutton.FileBrowseButtonWithHistory):

    def OnBrowse(self, event = None):

        dialog = wx.DirDialog(self,
            message = self.dialogTitle,
            defaultPath = self.GetValue(),
            style = wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST | wx.DD_NEW_DIR_BUTTON,
        )

        if dialog.ShowModal() == wx.ID_OK:
            self.SetValue(dialog.GetPath())
        dialog.Destroy()



def get_file_path_widget(parent: wx.Window, label: str = "", is_folder = False):


    frame: Launcher = parent.GetTopLevelParent()


    def on_change(event):
        set_path_ctrl(widget, widget.GetValue(), check = os.path.isdir if is_folder else os.path.isfile)


    def on_menu(event):

        menu = get_path_ctrl_menu(widget)

        parent.PopupMenu(menu)
        menu.Destroy()


    def on_scroll(event: wx.MouseEvent):

        direction = 1 if event.GetWheelRotation() > 0 else -1

        if event.ControlDown():

            ctrl = widget.GetHistoryControl()

            history = widget.GetHistory()
            if not history:
                return

            try:
                index = history.index(ctrl.GetValue()) - direction
                if index >= len(history):
                    index = 0
            except ValueError:
                index = 0

            ctrl.SetValue(history[index])

        else:

            x, y = frame.scroll_panel.GetViewStart()
            delta = event.GetLinesPerAction() * direction

            frame.scroll_panel.Scroll(x, y - delta)


    if is_folder:
        cls = FolderBrowseButtonWithHistory
    else:
        cls = wx.lib.filebrowsebutton.FileBrowseButtonWithHistory


    widget = cls(parent, labelText = label, changeCallback = on_change)

    widget.SetDropTarget(File_Drop_Target(widget))
    widget.GetHistoryControl().Bind(wx.EVT_CONTEXT_MENU, on_menu)
    widget.GetHistoryControl().Bind(wx.EVT_MOUSEWHEEL, on_scroll)


    return widget


def get_settings_widget(parent: wx.Window, settings: settings_base.Settings):

    button = wx.Button(parent, label = "Edit")

    final_settings = settings._to_dict()


    def iter_arguments():

        for key in typing.get_type_hints(type(settings)):

            if key.startswith('_'):
                continue

            spec = settings._get_attribute_spec(key)

            path = [settings.__class__.__name__] + [key]

            yield common.Argument_Walk_Item(
                path,
                spec.default,
                spec,
                final_settings.get(key, common.SENTINEL),
                False
            )


    def on_configure(event):

        with program_ui.Property_Grid_Dialog(parent, iter_arguments()) as dialog:

            dialog.SetSize((1000, 800))
            dialog.SetTitle(f"Settings Edit — {settings.__class__.__name__}")
            dialog.CenterOnScreen()

            dialog.ShowModal()


        if not dialog.do_save:
            return

        if not dialog.changes:
            return

        for path, value in dialog.changes.items():
            common._replace_dictionary_argument_recursive(final_settings, path[1:], value)


    button.Bind(wx.EVT_BUTTON, on_configure)


    def GetValue():
        return final_settings

    button.GetValue = GetValue


    return button



class Program(wx.Panel):


    def __init__(self, parent, program_name: str):
        super().__init__(parent, style = wx.BORDER_THEME)

        self.widget_map: typing.Dict[str, wx.Window] = {}
        self.program_name = program_name

        self.init_ui()


    def init_ui(self):

        main_sizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(main_sizer)

        header_sizer = wx.BoxSizer(wx.HORIZONTAL)
        main_sizer.Add(header_sizer, 0, wx.EXPAND)

        label_widget = wx.StaticText(self, label = self.program_name)
        header_sizer.Add(label_widget, 1, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)

        delete_button = wx.Button(self, label = "X", size=(30, 30))
        delete_button.Bind(wx.EVT_BUTTON, self.on_delete)
        header_sizer.Add(delete_button, 0, wx.EXPAND | wx.ALL, 5)

        self.sizer = wx.BoxSizer(wx.VERTICAL)
        main_sizer.Add(self.sizer, 0, wx.EXPAND | wx.ALL, 5)


    def on_delete(self, event):

        frame: Launcher = self.GetTopLevelParent()
        frame.Freeze()

        parent: wx.lib.scrolledpanel.ScrolledPanel = self.GetParent()

        self.Destroy()

        parent.Layout()
        parent.SetupScrolling()

        frame.enable_start_button()

        frame.Thaw()


def get_program_panel(parent: wx.Window, function: typing.Callable, program_name: str):


    def get_type(parameter: inspect.Parameter):

        if parameter.annotation is not inspect._empty:
            return parameter.annotation
        elif parameter.default is not inspect._empty:
            return type(parameter.default)
        else:
            return None


    def get_value(parameter: inspect.Parameter):

        if parameter.default is not inspect._empty:
            return parameter.default
        else:
            parameter_type = get_type(parameter)

            if parameter_type is None:
                return None
            else:
                return parameter_type()


    panel = Program(parent, program_name)

    signature = inspect.signature(function)

    for name, parameter in signature.parameters.items():

        parameter_type = get_type(parameter)
        value = get_value(parameter)

        if name == 'blender_executable':
            widget = get_file_path_widget(panel)
        elif name.endswith('root'):
            widget = get_file_path_widget(panel, is_folder = True)
        elif parameter_type is str:
            widget = wx.TextCtrl(panel, value = value)
        elif parameter_type is bool:
            widget = wx.ToggleButton(panel, label = "Toggle")
            widget.SetValue(value)
        elif issubclass(parameter_type, settings_base.Settings):
            widget = get_settings_widget(panel, settings = value if value else parameter_type())
        else:
            continue

        label = f"{name.replace('_', ' ').title()}:"

        label_widget = wx.StaticText(panel, label = label)
        panel.sizer.Add(label_widget , 0, wx.EXPAND | wx.ALL, 1)

        panel.sizer.Add(widget, 0, wx.EXPAND | wx.ALL, 1)
        panel.widget_map[name] = widget


    return panel


class Launcher(wx.Frame):


    def __init__(self, programs: typing.Dict[str, typing.Tuple[typing.Callable, typing.Callable]]):

        super().__init__(None, title = "Blend Converter GUI Launcher", size=(700, 800))

        self.programs = programs

        self.init_ui()


        self.config = {}

        self.config_file = os.path.join(ROOT, 'launcher.json')
        if os.path.exists(self.config_file):
            with open(self.config_file) as f:
                self.config.update(json.load(f))


        self.Bind(wx.EVT_CLOSE, self.on_close)

        self.Layout()
        self.Centre()


    def init_ui(self):

        sizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(sizer)


        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(button_sizer, 0, wx.EXPAND)


        self.start_button = wx.Button(self, label = 'Start')
        self.start_button.Bind(wx.EVT_BUTTON, self.on_start)
        button_sizer.Add(self.start_button, 1, wx.EXPAND | wx.ALL, 5)
        self.start_button.Enable(False)

        self.copy_button = wx.Button(self, label = 'Copy Command')
        self.copy_button.Bind(wx.EVT_BUTTON, self.on_copy_command)
        button_sizer.Add(self.copy_button, 1, wx.EXPAND | wx.ALL, 5)
        self.copy_button.Enable(False)

        self.create_shortcut_button = wx.Button(self, label = 'Create Shortcut')
        self.create_shortcut_button.Bind(wx.EVT_BUTTON, self.on_create_shortcut)
        button_sizer.Add(self.create_shortcut_button, 1, wx.EXPAND | wx.ALL, 5)
        self.create_shortcut_button.Enable(False)


        program_selector_sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(program_selector_sizer, 0, wx.EXPAND | wx.ALL)

        program_selector_sizer.Add(wx.StaticText(self, label = "Add program:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)

        self.program_selector = wx.ComboBox(self, choices = list(self.programs), style = wx.CB_READONLY)
        self.program_selector.Bind(wx.EVT_COMBOBOX, self.on_add_program)
        self.program_selector.Bind(wx.EVT_MOUSEWHEEL, lambda x: x)
        program_selector_sizer.Add(self.program_selector, 1, wx.EXPAND | wx.ALL, 5)


        self.scroll_panel = wx.lib.scrolledpanel.ScrolledPanel(self)
        sizer.Add(self.scroll_panel, 1, wx.EXPAND | wx.ALL, 5)
        self.scroll_panel.SetupScrolling()

        self.scroll_panel_sizer = wx.BoxSizer(wx.VERTICAL)
        self.scroll_panel.SetSizer(self.scroll_panel_sizer)


    def enable_start_button(self, event = None):

        do_enable = bool(self.scroll_panel_sizer.GetItemCount())

        self.start_button.Enable(do_enable)
        self.copy_button.Enable(do_enable)
        self.create_shortcut_button.Enable(do_enable)


    def get_program_collections(self):

        result: typing.List[common.Program_Collection] = []

        sizer_item: wx.SizerItem
        for sizer_item in self.scroll_panel_sizer.GetChildren():

            panel: Program = sizer_item.GetWindow()

            kwargs = {key: value.GetValue() for key, value in panel.widget_map.items()}
            result.append(common.Program_Collection.from_callable(*self.programs[panel.program_name], kwargs=kwargs))

        return result


    def get_command(self):

        return [
            sys.executable,
            os.path.join(ROOT, 'start.py'),
            json.dumps(self.get_program_collections(), default = lambda x: x._to_dict()),
        ]


    def on_start(self, event):

        self.save_history()

        env = os.environ.copy()

        for name in 'PROMPT', 'TERM_PROGRAM', 'TERM', 'TERMINAL_EMULATOR':
            env.pop(name, None)

        subprocess.Popen(self.get_command(), creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NEW_CONSOLE, start_new_session = True, env = env)


    def on_copy_command(self, event):

        import pyperclip

        pyperclip.copy(utils.get_command_from_list(self.get_command()))


    def on_create_shortcut(self, event):


        if os.name != 'nt':
            return


        with wxp_utils.Generic_Selector_Dialog(self, {'name': 'BC Template'}, title = f"Create Shortcut") as dialog:

            dialog.CenterOnScreen()

            if dialog.ShowModal() != wx.ID_OK:
                return

            dialog_data = dialog.get_data()

        name = dialog_data['name']
        if not name:
            return

        from blend_converter.windows import win_utils

        command = self.get_command()

        target_path = command[0]
        arguments = subprocess.list2cmdline(command[1:])

        shortcut_path = win_utils.create_shortcut(
            name = name,
            target_path = target_path,
            arguments = arguments,
            working_directory = os.getcwd(),
        )

        utils.os_show(shortcut_path)

        self.save_history()


    def write_config(self):

        with open(self.config_file, 'w') as f:
            json.dump(self.config, f, indent = 4)


    def save_history(self):

        history = self.config.setdefault('history', {})

        sizer_item: wx.SizerItem
        for sizer_item in self.scroll_panel_sizer.GetChildren():

            panel: Program = sizer_item.GetWindow()

            program_history = history.setdefault(panel.program_name, {})

            for widget_name, widget in panel.widget_map.items():

                if hasattr(widget, 'GetHistory'):

                    widget_history = program_history.get(widget_name, [])
                    widget_history = widget_history + widget.GetHistory()
                    widget_history = list(dict.fromkeys(widget_history))
                    program_history[widget_name] = widget_history


    def load_history(self, panel: Program):

        history = self.config.setdefault('history', {})

        for widget_name, widget in panel.widget_map.items():
            if hasattr(widget, 'SetHistory'):
                widget.SetHistory(history.get(panel.program_name, {}).get(widget_name, []))


    def on_close(self, event):
        self.save_history()
        self.write_config()
        event.Skip()


    def on_add_program(self, event):

        self.Freeze()

        program_name = self.program_selector.GetValue()
        self.program_selector.SetSelection(-1)

        panel = get_program_panel(self.scroll_panel, self.programs[program_name][1], program_name)

        self.load_history(panel)

        self.scroll_panel_sizer.Add(panel, 0, wx.EXPAND | wx.ALL, 5)

        self.scroll_panel.Layout()
        self.scroll_panel.SetupScrolling()

        self.scroll_panel.ScrollChildIntoView(panel)

        self.enable_start_button()

        self.Thaw()


def set_path_ctrl(ctrl: wx.lib.filebrowsebutton.FileBrowseButtonWithHistory, path: str, check: typing.Callable):

    control = ctrl.GetHistoryControl()
    history = ctrl.GetHistory()

    if not path:
        pass

    elif not os.access(path, os.R_OK):
        control.SetBackgroundColour(WX_RED_COLOR)

    elif not check(path):
        control.SetBackgroundColour(WX_RED_COLOR)

    elif path in history:
        control.SetBackgroundColour(WX_GREEN_COLOR)

    else:
        history.append(path)
        ctrl.SetHistory(tuple(history), selectionIndex = history.index(path))
        control.SetBackgroundColour(WX_GREEN_COLOR)

    control.Refresh()


def get_path_ctrl_menu(ctrl: wx.lib.filebrowsebutton.FileBrowseButtonWithHistory):

    menu = wx.Menu()

    control = ctrl.GetHistoryControl()

    path = control.GetStringSelection()

    delete_item = menu.Append(wx.ID_ANY, f"Delete from history: {path if path else '[SELECT AN ITEM FIRST]'}")
    delete_item.Enable(bool(path))

    def on_delete_from_history(event):
        history = ctrl.GetHistory()
        history.remove(path)
        ctrl.SetValue('')
        ctrl.SetHistory(tuple(history))
        control.SetBackgroundColour(WX_WHITE_COLOR)
        ctrl.Refresh()

        remove_from_history(ctrl, path)

    menu.Bind(wx.EVT_MENU, on_delete_from_history, delete_item)

    return menu


def remove_from_history(ctrl: wx.lib.filebrowsebutton.FileBrowseButtonWithHistory, path: str):

    main_frame: Launcher = ctrl.GetTopLevelParent()

    history = main_frame.config.get('history')
    if not history:
        return

    panel: Program = ctrl.GetParent()

    program_history = history.get(panel.program_name, {})
    if not program_history:
        return

    for widget_name, widget in panel.widget_map.items():

        if ctrl != widget:
            continue

        widget_history = program_history.get(widget_name, [])

        if path in widget_history:
            widget_history.remove(path)
