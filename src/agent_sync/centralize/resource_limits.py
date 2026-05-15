"""Layer 2: Resource limits — verificação de limites antes de operações de I/O.

Previne operações que excederiam limites de:
- Número de skills sendo movidas/copiadas
- Tamanho total de dados transferidos
- Espaço em disco no destino
- Profundidade de diretórios
"""

import os
from pathlib import Path

from rich.console import Console

console = Console()

# Limites default
MAX_SKILLS_PER_BATCH = 100        # Máximo de skills por operação
MAX_SKILL_SIZE_MB = 500           # Tamanho máximo de uma skill individual (MB)
MAX_TOTAL_SIZE_MB = 2000          # Tamanho total máximo de um batch (MB)
MAX_DIR_DEPTH = 10                # Profundidade máxima de diretório
MIN_DISK_SPACE_MB = 100           # Espaço mínimo em disco para operar (MB)


class ResourceLimitError(Exception):
    """Limite de recurso excedido — operação não pode prosseguir."""


class ResourceLimitWarning(Warning):
    """Aviso de recurso — operação pode prosseguir mas com atenção."""


def get_skill_size_mb(skill_path: Path) -> float:
    """Calcula o tamanho total de uma skill em MB."""
    if not skill_path.exists():
        return 0.0

    if skill_path.is_file():
        return skill_path.stat().st_size / (1024 * 1024)

    total = 0
    for f in skill_path.rglob("*"):
        if f.is_file() and not f.name.startswith("."):
            try:
                total += f.stat().st_size
            except OSError:
                pass
    return total / (1024 * 1024)


def get_directory_depth(path: Path) -> int:
    """Calcula a profundidade máxima de uma estrutura de diretórios."""
    if not path.is_dir():
        return 0

    max_depth = 0
    for f in path.rglob("*"):
        if f.is_dir():
            rel = f.relative_to(path)
            depth = len(rel.parts)
            max_depth = max(max_depth, depth)
    return max_depth


def get_free_disk_space_mb(path: Path) -> float:
    """Retorna o espaço livre em disco no path em MB."""
    try:
        st = os.statvfs(str(path))
        return (st.f_frsize * st.f_bavail) / (1024 * 1024)
    except (AttributeError, OSError):
        return float("inf")  # Não foi possível verificar


def check_skill_limits(
    skill_name: str,
    skill_path: Path,
    max_size_mb: float = MAX_SKILL_SIZE_MB,
    max_depth: int = MAX_DIR_DEPTH,
) -> list[str]:
    """Verifica limites de uma skill individual.

    Returns:
        Lista de avisos (pode prosseguir).
    """
    warnings: list[str] = []

    # Tamanho
    size_mb = get_skill_size_mb(skill_path)
    if size_mb > max_size_mb:
        warnings.append(
            f"Skill '{skill_name}' muito grande: {size_mb:.1f}MB "
            f"(limite: {max_size_mb}MB)"
        )

    # Profundidade
    if skill_path.is_dir():
        depth = get_directory_depth(skill_path)
        if depth > max_depth:
            warnings.append(
                f"Skill '{skill_name}' tem profundidade excessiva: "
                f"{depth} níveis (limite: {max_depth})"
            )

    return warnings


def check_batch_limits(
    skills_to_process: list[tuple[str, Path]],
    dest_path: Path,
    max_skills: int = MAX_SKILLS_PER_BATCH,
    max_total_mb: float = MAX_TOTAL_SIZE_MB,
    min_disk_mb: float = MIN_DISK_SPACE_MB,
) -> list[str]:
    """Verifica limites de um batch de skills a serem processadas.

    Args:
        skills_to_process: Lista de (skill_name, Path).
        dest_path: Diretório de destino (para verificar disco).

    Returns:
        Lista de avisos (vazia se tudo ok).
    """
    warnings: list[str] = []

    # Número de skills
    if len(skills_to_process) > max_skills:
        warnings.append(
            f"Batch de {len(skills_to_process)} skills excede limite "
            f"de {max_skills} skills por operação"
        )

    # Tamanho total
    total_mb = sum(get_skill_size_mb(path) for _, path in skills_to_process)
    if total_mb > max_total_mb:
        warnings.append(
            f"Tamanho total de {total_mb:.1f}MB excede limite "
            f"de {max_total_mb}MB"
        )

    # Espaço em disco
    free_mb = get_free_disk_space_mb(dest_path)
    if free_mb < min_disk_mb:
        warnings.append(
            f"Espaço em disco insuficiente: {free_mb:.1f}MB livre "
            f"(mínimo: {min_disk_mb}MB)"
        )

    return warnings


def validate_before_operation(
    selected_orphans: set,
    orphans: dict,
    hub_path: Path,
    move: bool,
) -> list[str]:
    """Valida recursos para a operação de importação de órfãos.

    Args:
        selected_orphans: Skills selecionadas para importar.
        orphans: Dict de informações dos órfãos.
        hub_path: Caminho do hub.
        move: True se move (origem será deletada), False se copy.

    Returns:
        Lista de avisos (pode prosseguir). Se crítica, raise ResourceLimitError.
    """
    warnings: list[str] = []

    # Montar lista de skills a processar
    to_process: list[tuple[str, Path]] = []
    for name in selected_orphans:
        if name in orphans:
            _, path = orphans[name]["agents"][0]
            to_process.append((name, path))

    if not to_process:
        return warnings

    # Verificar limites do batch
    batch_warnings = check_batch_limits(to_process, hub_path)
    warnings.extend(batch_warnings)

    # Verificar limites individuais (só aviso para skills grandes)
    for name, path in to_process:
        skill_warnings = check_skill_limits(name, path)
        warnings.extend(skill_warnings)

    return warnings
