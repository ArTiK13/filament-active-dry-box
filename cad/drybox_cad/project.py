"""Repository paths shared by CAD entry points, independent of the working directory."""
import hashlib
from pathlib import Path

CAD_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = CAD_ROOT.parent
OUTPUT_ROOT = REPO_ROOT / 'build' / 'cad'
PARAMETERS_FILE = CAD_ROOT / 'parameters' / 'default.json'
RENDER_NAMES = (
    'assembly_dry.png', 'assembly_regeneration.png', 'bin_layout.png',
    'cutaway.png', 'service_exploded.png', 'valve_detail.png',
)


def source_hashes():
    """Fingerprint the CAD code, locked environment and editable parameter input."""
    files = [*CAD_ROOT.glob('*.py'), *sorted((CAD_ROOT / 'drybox_cad').glob('*.py')),
             CAD_ROOT / 'requirements.lock.txt', PARAMETERS_FILE]
    return {str(p.relative_to(REPO_ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(files)}
