from inline_snapshot import snapshot

from .test_loader import check_script


def test_exec():
    check_script(
        {
            "test_pck/__init__.py": "",
            "test_pck/a.py": "a='some text'",
            "test_pck/b.py": """
from .a import a
def test():
    exec('print(a)')
""",
        },
        """
from test_pck.b import test

test()

    """,
        transformed_stdout=snapshot("<equal to normal>"),
        transformed_stderr=snapshot("<equal to normal>"),
        normal_stdout=snapshot(
            """\
some text
"""
        ),
        normal_stderr=snapshot(""),
    )
