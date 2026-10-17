"""Write one stage's section of docs/RESULTS.md without touching the other stages' sections."""

from pathlib import Path


def write_section(heading: str, body: str, path: str = "docs/RESULTS.md") -> None:
    """Replace the section starting with `heading` (a '## ...' line), or append it."""
    file = Path(path)
    text = file.read_text() if file.exists() else "# Results\n"
    lines = text.splitlines()
    start = next((i for i, line in enumerate(lines) if line.strip() == heading), None)
    new = [heading, ""] + body.strip("\n").splitlines() + [""]
    if start is None:
        lines += [""] + new
    else:
        end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
        lines[start:end] = new
    file.write_text("\n".join(lines).rstrip() + "\n")
