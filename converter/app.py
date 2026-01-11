""" The asset conversion app. """

import sys
import os
import time
import typing


if typing.TYPE_CHECKING:
    from blend_converter import updater


def except_hook(exc_type, exc_value, exc_traceback):
    import traceback
    traceback.print_exception(exc_type, exc_value, exc_traceback)
    sys.excepthook = sys.__excepthook__

    print()
    input('Press Enter to exit.')


def get_func_name(entry: 'updater.Program_Entry'):
    return getattr(entry.program, '_prog_type', 'NONE')


def main(file_and_getter_pairs: typing.List[typing.Tuple[str, str]]):

    is_using_terminal = not {'PROMPT', 'TERM_PROGRAM', 'TERM', 'TERMINAL_EMULATOR'}.isdisjoint(os.environ)

    if not is_using_terminal:
        sys.excepthook = except_hook

    from blend_converter.gui import updater_ui
    from blend_converter import updater
    updater.UPDATE_DELAY = 0

    print('conversion app start:', time.strftime('%Y.%m.%d %H:%M:%S'))
    columns = [
        ('func', 170, get_func_name),
    ]
    app = updater_ui.Main_Frame.get_app(file_and_getter_pairs, columns)

    app.main_frame.updater.total_max_parallel_executions = 8
    app.main_frame.updater.default_max_parallel_executions = 2
    app.main_frame.updater.set_max_parallel_executions_per_program_tag('gltf', 8)
    app.main_frame.updater.set_max_parallel_executions_per_program_tag('unreal', 1)

    if not is_using_terminal:
        sys.excepthook = sys.__excepthook__

    app.MainLoop()


if __name__ == '__main__':

    ROOT = os.path.join(os.path.dirname(__file__))

    programs = dict(
        static = (os.path.join(ROOT, 'programs', 'bake.py'), 'get_static_programs'),
        skeletal = (os.path.join(ROOT, 'programs', 'bake.py'), 'get_skeletal_programs'),
        godot = (os.path.join(ROOT, 'programs', 'godot.py'), 'get_programs'),
        unreal = (os.path.join(ROOT, 'programs', 'unreal_engine.py'), 'get_programs'),
        skin_test = (os.path.join(ROOT, 'programs', 'skin_test.py'), 'get_programs'),
        skin_proxy = (os.path.join(ROOT, 'programs', 'skin_proxy.py'), 'get_programs'),
        prebake = (os.path.join(ROOT, 'programs', 'prebake.py'), 'get_programs'),
        rig = (os.path.join(ROOT, 'programs', 'rig.py'), 'get_programs'),
    )

    print(sys.argv)
    print()

    names = []

    for arg in sys.argv[1:]:

        if arg.startswith('_'):
            break

        names.append(arg)

    if not names:

        for name, path in programs.items():
            print(name + "\n\t" + str(path))

        print()
        print("Must enter the names as the command line arguments. E.g.: static skeletal godot.")
        print()
        input("Press Enter to exit.")

    else:
        main([programs[n] for n in names])
