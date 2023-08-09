import sphinx
from docutils import nodes
from sphinx.application import Sphinx
from typing import Any

def insert_progression_note(app: Sphinx, doctree: nodes.document) -> None:
    msg = "Translation status of this document görr: |translation progress|"

    new_note = nodes.note()
    new_par = nodes.paragraph()
    new_text = nodes.Text(msg)
    new_par += new_text
    new_note += new_par
    doctree.insert(0, new_note)
    print(doctree.children[1])


def setup(app: Sphinx) -> dict[str, Any]:
    app.connect('doctree-read', insert_progression_note)
    return {
        'version': sphinx.__display_version__,
        'env_version': 2,
        'parallel_read_safe': True,
    }
