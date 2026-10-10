"""Keep user inputs safe from upstream's temporary-file cleanup policy."""
from pathlib import Path
import shutil
import tempfile


def translate_preserving_source(translate, input_file, params):
    with tempfile.TemporaryDirectory(prefix='freepdf-translate-') as working:
        staged = Path(working) / Path(input_file).name
        shutil.copy2(input_file, staged)
        return translate(files=[str(staged)], **params)
