"""Package source and results, optionally including the session's raw images."""

from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

from legocam import read_json

PROJECT = Path(__file__).resolve().parent


def package(session, include_images=False):
    output = PROJECT / "deliverables" / "LegoCam.zip"
    output.parent.mkdir(exist_ok=True)
    files = set()
    for pattern in (
        "*.py",
        "*.md",
        "*.ps1",
        "requirements*.txt",
        "reference_blocks.csv",
        "quick_validation.json",
        ".gitignore",
    ):
        files.update(PROJECT.glob(pattern))
    files.update(path for path in (PROJECT / "examples").rglob("*") if path.is_file())
    files.update(
        path
        for path in (PROJECT / "legacy").rglob("*")
        if path.is_file() and path.suffix in (".py", ".md")
    )
    report = PROJECT / "deliverables" / "LegoCam_report.html"
    if report.exists():
        files.add(report)
    if session.exists():
        for path in session.rglob("*"):
            if path.is_file() and path.suffix in (".json", ".csv", ".md", ".html"):
                files.add(path)
        if include_images:
            for path in (session / "records").glob("*.json"):
                for image in read_json(path).get("images", []):
                    resolved = (session / image).resolve()
                    if not resolved.is_relative_to(PROJECT):
                        raise ValueError("Image path leaves the project directory")
                    if not resolved.exists():
                        raise ValueError(f"Missing raw image: {resolved}")
                    files.add(resolved)
                    if resolved.with_name("overlay.png").exists():
                        files.add(resolved.with_name("overlay.png"))
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        for path in sorted(files):
            archive.write(path, "LegoCam/" + path.resolve().relative_to(PROJECT).as_posix())
    print(
        f"Saved {output}. Raw images {'included' if include_images else 'excluded; add --include-images for a full backup'}."
    )
    return output


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", type=Path, default=Path("sessions/reused"))
    parser.add_argument("--include-images", action="store_true")
    args = parser.parse_args()
    package(args.session, args.include_images)
