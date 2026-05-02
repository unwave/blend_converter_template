import typing
import os
import sys
import subprocess

import wx


from blend_converter import tool_settings
from blend_converter import utils


ROOT = os.path.dirname(os.path.realpath(__file__))


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


def get_shortcut_target(path: str):

    cmd = [
        'powershell',
        '-NoProfile',
        '-NonInteractive',
        '-WindowStyle',
        'Hidden',
        '-Command',
        '& { param($p); (new-object -com wscript.shell).CreateShortCut($p).Targetpath }',
        '-p',
        "'" + path + "'",
    ]


    print("CLI:", utils.get_command_from_list(cmd))

    try:
        return subprocess.check_output(cmd, text = True, creationflags = subprocess.CREATE_NO_WINDOW).strip()
    except subprocess.CalledProcessError as e:
        print(e)
        return None


class File_Drop_Target(wx.FileDropTarget):


    def __init__(self, ctrl: wx.FilePickerCtrl):
        super().__init__()
        self.ctrl = ctrl


    def OnDropFiles(self, x, y, filenames):

        path: str = filenames[0]

        if os.name == 'nt' and path.lower().endswith('.lnk'):
            path = get_shortcut_target(path)
            if path is None:
                return False

        self.ctrl.SetPath(path)

        return True



class Launcher(wx.Frame):


    result: Launch_Options = None


    def __init__(self, program_names: typing.List[str]):

        super().__init__(None, title = "Blend Converter GUI Launcher", size=(430, 600))

        panel = wx.Panel(self)

        sizer = wx.BoxSizer(wx.VERTICAL)

        self.checked_programs: typing.List[str] = []

        self.program_names = program_names


        sizer.Add(wx.StaticText(panel, label = 'Blender:') , 0, wx.ALL | wx.EXPAND, 5)

        self.blender_ctrl = wx.FilePickerCtrl(panel)
        sizer.Add(self.blender_ctrl , 0, wx.ALL | wx.EXPAND, 5)

        self.blender_ctrl.SetDropTarget(File_Drop_Target(self.blender_ctrl))


        sizer.Add(wx.StaticText(panel, label = 'Asset Root Folder:') , 0, wx.ALL | wx.EXPAND, 5)

        self.root_ctrl = wx.DirPickerCtrl(panel)
        sizer.Add(self.root_ctrl , 0, wx.ALL | wx.EXPAND, 5)

        self.root_ctrl.SetDropTarget(File_Drop_Target(self.root_ctrl))


        sizer.Add(wx.StaticText(panel, label = 'Programs:') , 0, wx.ALL | wx.EXPAND, 5)

        self.programs_ctrl = wx.CheckListBox(panel)
        sizer.Add(self.programs_ctrl, 1, wx.ALL | wx.EXPAND, 5)
        self.programs_ctrl.Bind(wx.EVT_CHECKLISTBOX, self.on_toggle)
        self.programs_ctrl.AppendItems(program_names)


        self.start_button = wx.Button(panel, label = 'Start')
        self.start_button.Bind(wx.EVT_BUTTON, self.on_start)
        sizer.Add(self.start_button, 0, wx.ALL | wx.EXPAND, 5)
        self.start_button.Enable(False)


        self.copy_button = wx.Button(panel, label = 'Copy Start Command')
        self.copy_button.Bind(wx.EVT_BUTTON, self.on_copy_command)
        sizer.Add(self.copy_button, 0, wx.ALL | wx.EXPAND, 5)
        self.copy_button.Enable(False)


        panel.SetSizerAndFit(sizer)
        self.Centre()


    def on_toggle(self, event):
        self.start_button.Enable(bool(self.programs_ctrl.GetCheckedItems()))
        self.copy_button.Enable(bool(self.programs_ctrl.GetCheckedItems()))


    def get_command(self):

        options =  Launch_Options(
            program_names = [self.program_names[i] for i in self.programs_ctrl.GetCheckedItems()],
            blender_executable = self.blender_ctrl.GetPath(),
            main_root = self.root_ctrl.GetPath(),
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
