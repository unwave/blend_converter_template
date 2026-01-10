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

    if not is_using_terminal:
        sys.excepthook = sys.__excepthook__

    app.MainLoop()


if __name__ == '__main__':

    ROOT = os.path.join(os.path.dirname(__file__))

    names = [
        (os.path.join(ROOT, 'programs', 'bake.py'), 'get_programs'),
        (os.path.join(ROOT, 'programs', 'godot.py'), 'get_programs'),
        (os.path.join(ROOT, 'programs', 'export.py'), 'get_anim_programs'),
        (os.path.join(ROOT, 'programs', 'extra.py'), 'get_programs'),
        (os.path.join(ROOT, 'programs', 'prebake.py'), 'get_programs'),
    ]

    print(sys.argv)

    numbers = []

    for arg in sys.argv[1:]:

        try:
            n = int(arg)
            assert len(names) >= n > 0
            numbers.append(n)
        except (ValueError, AssertionError):
            break

    if not numbers:

        for i, name in enumerate(names, start=1):
            print(f"{i}) {name}")

        print("Enter the numbers, e.g.: 1 2 3.")

    else:
        main([names[int(n) - 1] for n in numbers])
