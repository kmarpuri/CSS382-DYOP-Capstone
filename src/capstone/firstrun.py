"""First-run setup: install Ollama (with consent) and pull the model.

The pipeline:

1. Detect the local LLM stack.
   * Is the ``ollama`` binary on ``PATH``?
   * Is the daemon responding?
   * Is *any* chat-capable model already installed?

2. If anything's missing, **ask the user** before doing anything. We
   never download multi-GB models or install system binaries without
   explicit consent.

3. Stream a rich progress bar during ``ollama pull`` so the user can
   see what's happening.

A small marker file at ``~/.capstone/first_run_done`` records that
setup has completed so we don't re-prompt every session.
"""

from __future__ import annotations

import logging
import os
import platform
import shutil
import subprocess
import time
from pathlib import Path

import click

logger = logging.getLogger(__name__)

OLLAMA_INSTALL_SH = "https://ollama.com/install.sh"
OLLAMA_DOWNLOAD_URL = "https://ollama.com/download"


# ── Marker file ─────────────────────────────────────────────────────────

def _marker_path() -> Path:
    try:
        from platformdirs import user_data_dir
        base = Path(user_data_dir("capstone", appauthor=False))
    except ImportError:
        base = Path.home() / ".capstone"
    return base / "first_run_done"


def _mark_done() -> None:
    p = _marker_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(time.strftime("%Y-%m-%dT%H:%M:%S%z\n"))


def is_first_run() -> bool:
    return not _marker_path().exists()


# ── Detection ───────────────────────────────────────────────────────────

def ollama_binary_present() -> bool:
    return shutil.which("ollama") is not None


def ollama_daemon_running(host: str | None = None) -> bool:
    """Returns True if the Ollama daemon is responsive."""
    try:
        import ollama
    except ImportError:
        return False
    try:
        client = ollama.Client(host=host) if host else ollama
        client.list()
        return True
    except Exception:
        return False


def installed_models(host: str | None = None) -> list[str]:
    """List names of chat-capable models installed in Ollama (skipping embeddings)."""
    try:
        import ollama
        client = ollama.Client(host=host) if host else ollama
        data = client.list()
    except Exception:
        return []

    models = getattr(data, "models", None)
    if models is None and isinstance(data, dict):
        models = data.get("models", [])
    out: list[str] = []
    for entry in models or []:
        name = (
            getattr(entry, "model", None)
            or getattr(entry, "name", None)
            or (entry.get("model") or entry.get("name") if isinstance(entry, dict) else None)
        )
        if not name:
            continue
        if any(h in name.lower() for h in ("embed", "embedding", "bge", "nomic-embed")):
            continue
        out.append(name)
    return out


# ── Install Ollama ──────────────────────────────────────────────────────

def install_ollama(*, ask: bool = True, console=None) -> bool:
    """Best-effort cross-platform install of the Ollama binary.

    Returns True on success. On Windows we can only open the download
    page in a browser — automation isn't safe there.
    """
    from rich.console import Console
    console = console or Console()

    if ollama_binary_present():
        return True

    system = platform.system()
    machine = platform.machine()

    console.print(
        "[bold yellow]Ollama is not installed.[/bold yellow] "
        "It's a local LLM runtime that runs entirely on your machine."
    )
    console.print(f"  Platform: {system} ({machine})")

    if system == "Darwin":
        method, command = _macos_install_plan()
    elif system == "Linux":
        method, command = "shell", f'curl -fsSL "{OLLAMA_INSTALL_SH}" | sh'
    elif system == "Windows":
        method, command = "browser", OLLAMA_DOWNLOAD_URL + "/windows"
    else:
        console.print(f"[red]Unsupported platform {system!r}.[/red] "
                      f"Install Ollama manually from {OLLAMA_DOWNLOAD_URL}.")
        return False

    console.print(f"  Install method: [bold]{method}[/bold]")
    console.print(f"  Command:        [dim]{command}[/dim]")

    if ask and not click.confirm("Proceed?", default=True):
        console.print(
            "[dim]Skipped Ollama install. "
            "You can run 'capstone setup' later, or install manually "
            f"from {OLLAMA_DOWNLOAD_URL}.[/dim]"
        )
        return False

    if method == "browser":
        import webbrowser
        webbrowser.open(command)
        console.print(
            "[yellow]Opened the Ollama download page in your browser. "
            "Run 'capstone setup' again once it's installed.[/yellow]"
        )
        return False

    return _run_shell_install(command, console)


def _macos_install_plan() -> tuple[str, str]:
    """Pick the best macOS install path: brew if available, else the install.sh script."""
    if shutil.which("brew"):
        return "homebrew", "brew install ollama"
    return "shell", f'curl -fsSL "{OLLAMA_INSTALL_SH}" | sh'


def _run_shell_install(command: str, console) -> bool:
    """Run an install command, streaming output to the console."""
    console.print(f"[bold]Running:[/bold] {command}\n")
    try:
        result = subprocess.run(command, shell=True, check=False)
    except KeyboardInterrupt:
        console.print("\n[yellow]Aborted by user.[/yellow]")
        return False

    if result.returncode != 0:
        console.print(f"[red]Install command failed with exit code {result.returncode}.[/red]")
        console.print(
            f"You can install Ollama manually from {OLLAMA_DOWNLOAD_URL}, "
            f"then re-run [bold]capstone setup[/bold]."
        )
        return False

    if not ollama_binary_present():
        console.print(
            "[yellow]The install command finished but the 'ollama' binary "
            "still isn't on your PATH. You may need to open a new terminal "
            "or add /usr/local/bin to PATH.[/yellow]"
        )
        return False

    console.print("[green]✓ Ollama installed.[/green]")
    return True


# ── Start the daemon ───────────────────────────────────────────────────

def start_ollama_daemon(console=None, *, wait_seconds: float = 5.0) -> bool:
    """Spawn ``ollama serve`` if the daemon isn't already running."""
    from rich.console import Console
    console = console or Console()

    if ollama_daemon_running():
        return True
    if not ollama_binary_present():
        return False

    console.print("[dim]Starting the Ollama daemon...[/dim]")
    try:
        # Detach so the daemon outlives our process.
        subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError as e:
        console.print(f"[red]Could not start ollama daemon: {e}[/red]")
        return False

    deadline = time.time() + wait_seconds
    while time.time() < deadline:
        if ollama_daemon_running():
            console.print("[green]✓ Ollama daemon is up.[/green]")
            return True
        time.sleep(0.3)

    console.print(
        "[yellow]Started 'ollama serve' but the daemon didn't respond "
        f"within {wait_seconds:.0f}s. Try running 'ollama serve' manually.[/yellow]"
    )
    return False


# ── Pull a model ───────────────────────────────────────────────────────

def pull_model(
    model: str,
    *,
    ask: bool = True,
    console=None,
    host: str | None = None,
) -> bool:
    """Pull ``model`` via Ollama. Streams progress to the console.

    Returns True if the model is available afterwards.
    """
    from rich.console import Console
    console = console or Console()

    if model in installed_models(host=host):
        return True

    console.print(
        f"\n[bold]Model[/bold] [cyan]{model}[/cyan] "
        f"is not installed. Downloads are typically 4–20 GB."
    )
    if ask and not click.confirm(f"Pull {model} now?", default=True):
        console.print("[dim]Skipped model pull.[/dim]")
        return False

    try:
        import ollama
        from rich.progress import (
            BarColumn,
            DownloadColumn,
            Progress,
            TextColumn,
            TimeRemainingColumn,
        )
    except ImportError as e:
        console.print(f"[red]ollama Python client missing: {e}[/red]")
        return False

    client = ollama.Client(host=host) if host else ollama

    progress = Progress(
        TextColumn("[bold blue]{task.fields[status]}"),
        BarColumn(),
        DownloadColumn(),
        TextColumn("•"),
        TimeRemainingColumn(),
        console=console,
        transient=False,
    )

    tasks: dict[str, int] = {}
    try:
        with progress:
            for chunk in client.pull(model, stream=True):
                # chunk fields: status, digest, total, completed
                status = (
                    getattr(chunk, "status", None)
                    or (chunk.get("status") if isinstance(chunk, dict) else None)
                    or ""
                )
                digest = (
                    getattr(chunk, "digest", None)
                    or (chunk.get("digest") if isinstance(chunk, dict) else None)
                    or status
                )
                total = (
                    getattr(chunk, "total", None)
                    or (chunk.get("total") if isinstance(chunk, dict) else None)
                    or 0
                )
                completed = (
                    getattr(chunk, "completed", None)
                    or (chunk.get("completed") if isinstance(chunk, dict) else None)
                    or 0
                )

                key = digest or status or "main"
                if key not in tasks and total:
                    tasks[key] = progress.add_task(
                        "download", total=total, status=status,
                    )
                if key in tasks and total:
                    progress.update(
                        tasks[key], completed=completed, total=total, status=status,
                    )
    except Exception as e:
        console.print(f"[red]Pull failed: {e}[/red]")
        return False

    if model in installed_models(host=host):
        console.print(f"[green]✓ {model} ready.[/green]")
        return True
    console.print(f"[red]Pull finished but {model} doesn't appear installed.[/red]")
    return False


# ── Top-level entry point ──────────────────────────────────────────────

def run_first_run_setup(
    *,
    ask: bool = True,
    auto_pull: bool = True,
    console=None,
    model: str | None = None,
) -> bool:
    """Walk through the first-run wizard. Returns True if the stack is usable.

    Steps:
      1. Detect hardware → recommended model.
      2. Install Ollama if missing (with consent).
      3. Start the daemon if it isn't running.
      4. Pull the recommended model if no chat model is installed
         (with consent).
      5. Write the first-run marker.
    """
    from rich.console import Console

    from capstone.llm.hardware import detect_hardware_tier

    console = console or Console()

    hw = detect_hardware_tier()
    target_model = model or os.environ.get("CAPSTONE_LLM_MODEL") or hw.model

    console.print("\n[bold magenta]Capstone — first-time setup[/bold magenta]")
    console.print(
        f"  RAM: {hw.ram_gb:.1f} GB · VRAM: {hw.vram_gb:.1f} GB · Tier {hw.tier}\n"
        f"  Recommended model: [cyan]{target_model}[/cyan]\n"
        f"  Notes: {hw.notes}"
    )

    # Step 1: Ollama binary
    if not ollama_binary_present():
        if not install_ollama(ask=ask, console=console):
            return False

    # Step 2: daemon
    if not ollama_daemon_running():
        if not start_ollama_daemon(console=console):
            console.print(
                "[yellow]Continuing without a daemon — "
                "you can start it later with 'ollama serve'.[/yellow]"
            )
            return False

    # Step 3: model
    existing = installed_models()
    if target_model in existing:
        console.print(f"[green]✓ {target_model} is already installed.[/green]")
    elif existing:
        console.print(
            f"[green]✓ Found an installed model: {existing[0]}.[/green] "
            f"Capstone will fall back to it automatically. "
            f"To use the recommended {target_model}, run "
            f"[bold]ollama pull {target_model}[/bold]."
        )
        if auto_pull and click.confirm(
            f"Pull {target_model} now? (downloads several GB)", default=False
        ):
            pull_model(target_model, ask=False, console=console)
    else:
        # Nothing installed — pull the recommended model
        if not pull_model(target_model, ask=ask, console=console):
            console.print(
                "[red]No chat model available. The LLM layer will be disabled "
                "until you pull one.[/red]"
            )
            return False

    _mark_done()
    console.print("[bold green]Setup complete.[/bold green]\n")
    return True
