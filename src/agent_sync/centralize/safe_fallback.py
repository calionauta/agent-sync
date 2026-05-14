"""Layer 3: Safe fallback — backup e rollback para operações de centralize.

Cria snapshots do estado do hub antes de modificações e permite
restauração em caso de falha.
"""

import json
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional

from rich.console import Console

console = Console()

SNAPSHOT_DIR_NAME = ".centralize-snapshots"


class Snapshot:
    """Snapshot do estado do hub antes de uma operação de centralize."""

    def __init__(self, hub_path: Path):
        self.hub_path = hub_path
        self.snapshot_dir = hub_path / SNAPSHOT_DIR_NAME
        self._backup_path: Optional[Path] = None
        self._manifest: dict = {}
        self._created = False

    def create(self, metadata: Optional[dict] = None) -> Path:
        """Cria um snapshot do estado atual do hub.

        Args:
            metadata: Metadados opcionais para o snapshot.

        Returns:
            Caminho do diretório de snapshot.

        Raises:
            RuntimeError: Se o snapshot não puder ser criado.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)
        self._backup_path = self.snapshot_dir / f"snapshot_{timestamp}"

        # Salvar manifest com metadados
        self._manifest = {
            "created_at": datetime.now().isoformat(),
            "hub_path": str(self.hub_path.resolve()),
            "snapshot_path": str(self._backup_path),
            "skills_count": 0,
            "skills": [],
            "metadata": metadata or {},
        }

        if not self.hub_path.exists():
            # Hub não existe — snapshot vazio
            self._backup_path.mkdir(parents=True, exist_ok=True)
            self._save_manifest()
            self._created = True
            return self._backup_path

        # Copiar todas as skills do hub para o backup
        try:
            self._backup_path.mkdir(parents=True, exist_ok=True)
            for item in self.hub_path.iterdir():
                if item.name.startswith("."):
                    continue  # Pular .snapshot_dir e outros ocultos
                dest = self._backup_path / item.name
                if item.is_dir():
                    shutil.copytree(item, dest)
                else:
                    shutil.copy2(item, dest)
                self._manifest["skills"].append(item.name)
                self._manifest["skills_count"] += 1

            self._save_manifest()
            self._created = True
            console.print(
                f"  [dim]📸 Snapshot: {self._manifest['skills_count']} skills "
                f"salvas em {self._backup_path.name}[/]"
            )
            return self._backup_path

        except Exception as e:
            # Limpar se algo falhar
            if self._backup_path and self._backup_path.exists():
                shutil.rmtree(self._backup_path)
            raise RuntimeError(f"Falha ao criar snapshot: {e}")

    def restore(self) -> int:
        """Restaura o hub para o estado do snapshot.

        Returns:
            Número de skills restauradas.

        Raises:
            RuntimeError: Se não há snapshot para restaurar.
        """
        if not self._created or not self._backup_path:
            raise RuntimeError("Nenhum snapshot disponível para restaurar")

        if not self._backup_path.exists():
            raise RuntimeError(f"Snapshot não encontrado: {self._backup_path}")

        # Limpar hub atual (exceto snapshots)
        if self.hub_path.exists():
            for item in self.hub_path.iterdir():
                if item.name == SNAPSHOT_DIR_NAME:
                    continue
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()
        else:
            self.hub_path.mkdir(parents=True, exist_ok=True)

        # Copiar de volta
        restored = 0
        for item in self._backup_path.iterdir():
            if item.name.startswith("."):
                continue
            dest = self.hub_path / item.name
            if item.is_dir():
                shutil.copytree(item, dest)
            else:
                shutil.copy2(item, dest)
            restored += 1

        console.print(
            f"  [green]♻️  Restauradas {restored} skills do snapshot "
            f"{self._backup_path.name}[/]"
        )
        return restored

    def cleanup(self, keep_last: int = 3) -> int:
        """Remove snapshots antigos, mantendo os N mais recentes.

        Args:
            keep_last: Número de snapshots mais recentes a manter.

        Returns:
            Número de snapshots removidos.
        """
        if not self.snapshot_dir.exists():
            return 0

        snapshots = sorted(
            [d for d in self.snapshot_dir.iterdir() if d.is_dir() and d.name.startswith("snapshot_")],
            reverse=True,
        )

        removed = 0
        for snap in snapshots[keep_last:]:
            try:
                shutil.rmtree(snap)
                removed += 1
            except OSError:
                pass

        return removed

    def _save_manifest(self) -> None:
        """Salva o manifest do snapshot."""
        if self._backup_path:
            manifest_path = self._backup_path / ".manifest.json"
            with open(manifest_path, "w") as f:
                json.dump(self._manifest, f, indent=2)

    @staticmethod
    def last_snapshot(hub_path: Path) -> Optional[dict]:
        """Retorna o manifest do snapshot mais recente, se houver.

        Returns:
            Dict com manifest ou None.
        """
        snap_dir = hub_path / SNAPSHOT_DIR_NAME
        if not snap_dir.exists():
            return None

        snapshots = sorted(
            [d for d in snap_dir.iterdir() if d.is_dir() and d.name.startswith("snapshot_")],
            reverse=True,
        )

        if not snapshots:
            return None

        manifest_path = snapshots[0] / ".manifest.json"
        if manifest_path.exists():
            try:
                return json.loads(manifest_path.read_text())
            except (json.JSONDecodeError, OSError):
                return None
        return None


def with_fallback(func):
    """Decorator que executa uma função com snapshot + fallback automático.

    Se a função lançar uma exceção, o hub é restaurado ao estado anterior.
    O snapshot é limpo após sucesso (mantendo últimos 3).

    Uso:
        @with_fallback
        def minha_operacao(hub_path, **kwargs):
            ...
    """
    from functools import wraps

    @wraps(func)
    def wrapper(hub_path: Path, *args, **kwargs):
        snap = Snapshot(hub_path)
        try:
            snap.create(metadata={"operation": func.__name__})
            result = func(hub_path, *args, **kwargs)
            snap.cleanup(keep_last=3)
            return result
        except Exception as e:
            console.print(f"\n[red]✗ Erro durante {func.__name__}: {e}[/]")
            console.print("[yellow]♻️  Restaurando snapshot anterior...[/]")
            try:
                snap.restore()
            except Exception as restore_err:
                console.print(f"[red]✗ Falha na restauração: {restore_err}[/]")
            raise

    return wrapper
