import typing
import os
import sys
import subprocess
import json

import wx
import wx.lib.filebrowsebutton

from blend_converter import tool_settings
from blend_converter import utils


ROOT = os.path.dirname(os.path.realpath(__file__))


WX_GREEN_COLOR = wx.Colour(200, 255, 200)
WX_RED_COLOR = wx.Colour(255, 200, 200)
WX_WHITE_COLOR = wx.Colour(255, 255, 255)


if typing.TYPE_CHECKING:
    import dataclasses
else:
    class dataclasses:
        dataclass = lambda x: x


@dataclasses.dataclass
class Launch_Options(tool_settings.Settings):

    program_names: typing.List[str] = None

    blender_executable: str = ''

    main_root: str = ''


def start_launcher(strings: typing.List[str]):

    app = wx.App()
    frame = Launcher(strings)
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



def get_file_path_widget(parent: wx.Window, label: str, is_folder = False):


    def on_change(event):
        set_path_ctrl(widget, widget.GetValue(), check = os.path.isdir if is_folder else os.path.isfile)


    def on_menu(event):

        menu = get_path_ctrl_menu(widget)

        parent.PopupMenu(menu)
        menu.Destroy()


    if is_folder:
        cls = FolderBrowseButtonWithHistory
    else:
        cls = wx.lib.filebrowsebutton.FileBrowseButtonWithHistory


    widget = cls(parent, labelText = label, changeCallback = on_change)

    widget.SetDropTarget(File_Drop_Target(widget))
    widget.GetHistoryControl().Bind(wx.EVT_CONTEXT_MENU, on_menu)


    return widget


class Launcher(wx.Frame):


    result: Launch_Options = None


    def __init__(self, program_names: typing.List[str]):

        super().__init__(None, title = "Blend Converter GUI Launcher", size=(600, 600))

        panel = wx.Panel(self)

        sizer = wx.BoxSizer(wx.VERTICAL)

        self.checked_programs: typing.List[str] = []

        self.program_names = program_names


        self.blender_ctrl = get_file_path_widget(panel, "Blender:")
        sizer.Add(self.blender_ctrl , 0, wx.ALL | wx.EXPAND, 5)

        self.root_ctrl = get_file_path_widget(panel, "Blends:", is_folder = True)
        sizer.Add(self.root_ctrl , 0, wx.ALL | wx.EXPAND, 5)


        sizer.Add(wx.StaticText(panel, label = 'Programs:') , 0, wx.ALL | wx.EXPAND, 5)

        self.programs_ctrl = wx.CheckListBox(panel)
        sizer.Add(self.programs_ctrl, 1, wx.ALL | wx.EXPAND, 5)
        self.programs_ctrl.Bind(wx.EVT_CHECKLISTBOX, self.on_toggle_programs_ctrl)
        self.programs_ctrl.AppendItems(program_names)


        self.start_button = wx.Button(panel, label = 'Start')
        self.start_button.Bind(wx.EVT_BUTTON, self.on_start)
        sizer.Add(self.start_button, 0, wx.ALL | wx.EXPAND, 5)
        self.start_button.Enable(False)


        self.copy_button = wx.Button(panel, label = 'Copy Start Command')
        self.copy_button.Bind(wx.EVT_BUTTON, self.on_copy_command)
        sizer.Add(self.copy_button, 0, wx.ALL | wx.EXPAND, 5)
        self.copy_button.Enable(False)


        self.config = wx.FileConfig(localFilename = os.path.join(ROOT, 'launcher.ini'))
        self.Bind(wx.EVT_CLOSE, self.on_close)
        self.apply_config()


        panel.SetSizerAndFit(sizer)
        self.Centre()


    def on_toggle_programs_ctrl(self, event = None):
        self.start_button.Enable(bool(self.programs_ctrl.GetCheckedItems()))
        self.copy_button.Enable(bool(self.programs_ctrl.GetCheckedItems()))


    def get_command(self):

        options =  Launch_Options(
            program_names = [self.program_names[i] for i in self.programs_ctrl.GetCheckedItems()],
            blender_executable = self.blender_ctrl.GetValue(),
            main_root = self.root_ctrl.GetValue(),
        )

        return [
            sys.executable,
            os.path.join(ROOT, 'start.py'),
            options._to_json(),
        ]


    def on_start(self, event):

        env = os.environ.copy()

        for name in 'PROMPT', 'TERM_PROGRAM', 'TERM', 'TERMINAL_EMULATOR':
            env.pop(name, None)

        subprocess.Popen(self.get_command(), creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NEW_CONSOLE, start_new_session = True, env = env)


    def on_copy_command(self, event):

        import pyperclip

        pyperclip.copy(utils.get_command_from_list(self.get_command()))


    def apply_config(self):
        user_input = json.loads(self.config.Read('user_input', '{}'))

        self.blender_ctrl.SetHistory(user_input.get('blender_ctrl_history', []))
        self.root_ctrl.SetHistory(user_input.get('root_ctrl_history', []))

        self.blender_ctrl.SetValue(user_input.get('blender_ctrl_value', ''))
        self.root_ctrl.SetValue(user_input.get('root_ctrl_value', ''))

        for name in user_input.get('checked_programs_names', []):
            self.programs_ctrl.Check(self.programs_ctrl.FindString(name))

        self.on_toggle_programs_ctrl()


    def save_config(self):
        user_input = dict(
            blender_ctrl_history = self.blender_ctrl.GetHistory(),
            root_ctrl_history = self.root_ctrl.GetHistory(),
            blender_ctrl_value = self.blender_ctrl.GetValue(),
            root_ctrl_value = self.root_ctrl.GetValue(),
            checked_programs_names = [self.program_names[i] for i in self.programs_ctrl.GetCheckedItems()],
        )
        self.config.Write('user_input', json.dumps(user_input))
        self.config.Flush()


    def on_close(self, event):
        self.save_config()
        event.Skip()



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

    menu.Bind(wx.EVT_MENU, on_delete_from_history, delete_item)

    return menu
