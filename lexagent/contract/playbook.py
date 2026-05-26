# Contract playbooks: stores a firm's past negotiating positions on key clauses.
#
# WHY YAML files in ~/.lexagent/playbooks/: same pattern as agents and skills —
# lawyers (or their ops team) can edit them in any text editor, git-track them,
# and share them across a firm without needing a database.
#
# A playbook captures: what clause, what our position is, why, and any precedents.
# During contract review, the active playbook is injected into the system prompt
# so the LLM can flag deviations from firm position automatically.

import uuid
from datetime import date
from pathlib import Path
from typing import Optional

import yaml


_BUNDLED_DIR = Path(__file__).parent / "defaults"
_USER_DIR_DEFAULT = "~/.lexagent/playbooks"


def _playbooks_dir(user_dir: str = _USER_DIR_DEFAULT) -> Path:
    return Path(user_dir).expanduser()


def list_playbooks(user_dir: str = _USER_DIR_DEFAULT) -> list[dict]:
    """Return all playbooks (bundled + user), sorted by name. User overrides bundled on ID clash."""
    bundled: dict[str, dict] = {}
    if _BUNDLED_DIR.exists():
        for f in _BUNDLED_DIR.glob("*.yaml"):
            pb = _load_file(f)
            if pb:
                pb["source"] = "bundled"
                bundled[pb["id"]] = pb

    user: dict[str, dict] = {}
    ud = _playbooks_dir(user_dir)
    if ud.exists():
        for f in ud.glob("*.yaml"):
            pb = _load_file(f)
            if pb:
                pb["source"] = "custom"
                user[pb["id"]] = pb

    merged = {**bundled, **user}
    return sorted(merged.values(), key=lambda x: x.get("name", x["id"]))


def load_playbook(playbook_id: str, user_dir: str = _USER_DIR_DEFAULT) -> Optional[dict]:
    """Load a single playbook by ID. User copy takes precedence over bundled."""
    ud = _playbooks_dir(user_dir)
    user_file = ud / f"{playbook_id}.yaml"
    if user_file.exists():
        pb = _load_file(user_file)
        if pb:
            pb["source"] = "custom"
            return pb

    bundled_file = _BUNDLED_DIR / f"{playbook_id}.yaml"
    if bundled_file.exists():
        pb = _load_file(bundled_file)
        if pb:
            pb["source"] = "bundled"
            return pb

    return None


def create_playbook(data: dict, user_dir: str = _USER_DIR_DEFAULT) -> Path:
    """Save a new playbook YAML to the user playbooks directory."""
    ud = _playbooks_dir(user_dir)
    ud.mkdir(parents=True, exist_ok=True)
    pb_id = data.get("id") or _slugify(data.get("name", str(uuid.uuid4())[:8]))
    data["id"] = pb_id
    if "created" not in data:
        data["created"] = str(date.today())
    path = ud / f"{pb_id}.yaml"
    path.write_text(yaml.dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return path


def delete_playbook(playbook_id: str, user_dir: str = _USER_DIR_DEFAULT) -> bool:
    """Delete a user playbook. Returns False if it's bundled or doesn't exist."""
    ud = _playbooks_dir(user_dir)
    target = ud / f"{playbook_id}.yaml"
    if target.exists():
        target.unlink()
        return True
    return False


def playbook_to_prompt(pb: dict) -> str:
    """Render a playbook as a system prompt block for injection into contract review."""
    lines = [
        f"## Firm Playbook — {pb.get('name', pb['id'])}",
        f"Contract type: {pb.get('contract_type', '—')}",
        "",
        "### Our Standard Positions",
    ]
    for pos in pb.get("positions", []):
        lines.append(f"**{pos.get('clause', '—')}**: {pos.get('our_position', '—')}")
        if pos.get("rationale"):
            lines.append(f"  Rationale: {pos['rationale']}")
    if pb.get("notes"):
        lines.append(f"\n### Notes\n{pb['notes']}")
    return "\n".join(lines)


def _load_file(path: Path) -> Optional[dict]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and "id" in data:
            return data
    except Exception:
        pass
    return None


def _slugify(text: str) -> str:
    import re
    return re.sub(r"[^a-z0-9_]", "_", text.lower().strip())[:40]
