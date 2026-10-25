"""Shared test setup: make the modules in web/ importable like on Toolforge."""
import re
import sys
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parents[1]
WEB_DIR = REPO_DIR / 'web'

if str(WEB_DIR) not in sys.path:
    sys.path.insert(0, str(WEB_DIR))

SCHEMA_DOC = REPO_DIR / 'sql' / 'schema.md'


def schema_sql(path=SCHEMA_DOC):
    """The DDL of the pb database: all ```sql blocks of sql/schema.md, in order."""
    return '\n'.join(re.findall(r'^```sql\n(.*?)^```$', path.read_text(), re.MULTILINE | re.DOTALL))
