# samuraizer_gui/ui/widgets/results_display/graph_utils.py

import logging
import os
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

def check_graphviz_installation() -> bool:
    """Check whether the Graphviz ``dot`` executable is available."""

    def _add_to_path(candidate: Path) -> bool:
        """Add ``candidate`` to PATH if it contains the dot binary."""

        try:
            if not candidate.exists():
                return False

            dot_binary = candidate / "dot.exe" if os.name == "nt" else candidate / "dot"
            if not dot_binary.exists():
                return False

            path = os.environ.get("PATH", "")
            if str(candidate) not in path.split(os.pathsep):
                os.environ["PATH"] = str(candidate) + os.pathsep + path
                logger.debug(f"Graphviz path added to PATH: {candidate}")
            return True
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug(f"Failed to append Graphviz path {candidate}: {exc}")
            return False

    try:
        # Fast path – ``shutil.which`` already respects PATH and PATHEXT.
        dot_path = shutil.which("dot")
        if dot_path:
            logger.debug(f"Graphviz 'dot' found at: {dot_path}")
        else:
            logger.debug("Graphviz 'dot' not found in PATH – trying common locations")

            common_paths = set()
            # Windows default locations
            if os.name == "nt":
                program_files = os.environ.get("PROGRAMFILES")
                program_files_x86 = os.environ.get("PROGRAMFILES(X86)")
                local_app_data = os.environ.get("LOCALAPPDATA")

                candidates = [
                    Path(r"C:\Graphviz\bin"),
                    Path(r"C:\Program Files\Graphviz\bin"),
                    Path(r"C:\Program Files (x86)\Graphviz\bin"),
                ]

                if program_files:
                    candidates.append(Path(program_files) / "Graphviz" / "bin")
                if program_files_x86:
                    candidates.append(Path(program_files_x86) / "Graphviz" / "bin")
                if local_app_data:
                    candidates.append(Path(local_app_data) / "Programs" / "Graphviz" / "bin")

                common_paths.update(candidates)
            else:
                # Typical Unix locations
                common_paths.update(
                    Path(p)
                    for p in ("/usr/bin", "/usr/local/bin", "/opt/homebrew/bin", "/opt/local/bin")
                )

            for candidate in common_paths:
                if _add_to_path(candidate):
                    dot_path = shutil.which("dot")
                    if dot_path:
                        break

        if not dot_path:
            logger.error("Graphviz 'dot' executable not found")
            return False

        # ``dot -V`` prints version information to stderr on Windows.
        result = subprocess.run([
            dot_path,
            "-V",
        ], capture_output=True, text=True, check=False)

        if result.returncode != 0:
            logger.warning(
                "Graphviz 'dot' returned non-zero exit code during version check: %s",
                result.stderr or result.stdout,
            )

        logger.debug(
            "Graphviz version output: %s",
            (result.stdout or "").strip() or (result.stderr or "").strip(),
        )
        return True

    except FileNotFoundError:
        logger.error("Graphviz 'dot' executable not accessible even after PATH adjustments")
        return False
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error(f"Error while checking Graphviz installation: {exc}")
        return False
