"""Layer 1: Input validation — validação de entrada para operações de centralize.

Garante que todos os parâmetros e caminhos são válidos antes de qualquer
operação de movimentação/cópia de skills.
"""

import os
import stat
from pathlib import Path
from typing import Optional

from rich.console import Console

console = Console()


class ValidationError(Exception):
    """Erro de validação — operação não pode prosseguir."""


class ValidationWarning(Warning):
    """Aviso de validação — operação pode prosseguir com ressalvas."""


def validate_hub_directory(hub_path: Path) -> list[str]:
    """Valida que o diretório hub (~/.agents/skills/) é acessível e gravável.

    Returns:
        Lista de warnings (vazia se tudo ok).

    Raises:
        ValidationError: Se o diretório não pode ser usado.
    """
    warnings: list[str] = []

    if not hub_path.exists():
        # Será criado durante centralize — não é erro
        return warnings

    if not hub_path.is_dir():
        raise ValidationError(
            f"Caminho do hub não é um diretório: {hub_path}"
        )

    # Verificar permissão de escrita
    try:
        test_file = hub_path / ".write_test"
        test_file.touch()
        test_file.unlink()
    except (OSError, PermissionError) as e:
        raise ValidationError(
            f"Sem permissão de escrita no hub: {hub_path} — {e}"
        )

    # Verificar espaço em disco (mínimo 10MB)
    try:
        st = os.statvfs(str(hub_path))
        free_bytes = st.f_frsize * st.f_bavail
        free_mb = free_bytes / (1024 * 1024)
        if free_mb < 10:
            raise ValidationError(
                f"Espaço em disco insuficiente no hub: {free_mb:.1f}MB livre "
                f"(mínimo 10MB)"
            )
    except AttributeError:
        # statvfs não disponível no Windows — ignorar
        pass
    except OSError as e:
        warnings.append(f"Não foi possível verificar espaço em disco: {e}")

    return warnings


def validate_skill_name(name: str) -> Optional[str]:
    """Valida que um nome de skill é aceitável para o sistema de arquivos.

    Returns:
        None se válido, string de erro se inválido.
    """
    if not name or name.strip() == "":
        return "Nome de skill não pode ser vazio"

    if len(name) > 128:
        return f"Nome de skill muito longo ({len(name)} chars, max 128)"

    # Verificar caracteres proibidos
    forbidden = ['/', '\\', ':', '*', '?', '"', '<', '>', '|', '\x00']
    for char in forbidden:
        if char in name:
            return f"Nome de skill contém caractere proibido: '{char}'"

    # Não pode começar com ponto (arquivo oculto)
    if name.startswith('.'):
        return "Nome de skill não pode começar com '.'"

    return None


def validate_skill_path(skill_path: Path) -> Optional[str]:
    """Valida que um caminho de skill existe e é legível.

    Returns:
        None se válido, string de erro se inválido.
    """
    if not skill_path.exists():
        return f"Skill não encontrada: {skill_path}"

    if skill_path.is_symlink():
        # Symlinks devem ser resolvidos antes
        try:
            target = skill_path.resolve()
            if not target.exists():
                return f"Symlink quebrado: {skill_path} → {target}"
        except (OSError, RuntimeError) as e:
            return f"Erro ao resolver symlink {skill_path}: {e}"

    if skill_path.is_dir():
        # Verificar SKILL.md
        sk = skill_path / "SKILL.md"
        if not sk.exists():
            # Não é erro — skill pode ser pasta com outros arquivos
            pass
        elif os.path.getsize(sk) == 0:
            return f"SKILL.md vazio em: {skill_path}"
        elif os.path.getsize(sk) > 1024 * 1024:
            return f"SKILL.md muito grande ({os.path.getsize(sk)} bytes) em: {skill_path}"

    return None


def validate_agent_directory(path: Path) -> Optional[str]:
    """Valida que o diretório de skills de um agente é acessível.

    Returns:
        None se válido, string de erro se inválido.
    """
    if not path.exists():
        # Agente pode não ter skills ainda — não é erro
        return None

    if not path.is_dir():
        return f"Caminho do agente não é um diretório: {path}"

    try:
        list(path.iterdir())
    except (OSError, PermissionError) as e:
        return f"Sem permissão de leitura no agente: {path} — {e}"

    return None


def collect_validation_errors(
    hub_path: Path,
    agent_skills: dict,
) -> tuple[list[str], list[str]]:
    """Valida todos os caminhos e nomes envolvidos na centralização.

    Args:
        hub_path: Caminho do diretório hub.
        agent_skills: Dict de {agent_name: [skill_paths]}.

    Returns:
        (erros, warnings) — listas de mensagens.
    """
    errors: list[str] = []
    warnings: list[str] = []

    # Validar hub
    try:
        hub_warnings = validate_hub_directory(hub_path)
        warnings.extend(hub_warnings)
    except ValidationError as e:
        errors.append(str(e))

    # Validar agentes e skills
    for agent_name, skill_data in agent_skills.items():
        if isinstance(skill_data, dict):
            paths = skill_data.get("paths", [])
            is_ext = skill_data.get("is_extension", False)
        else:
            paths = skill_data
            is_ext = False

        if is_ext:
            continue  # Extensões não são centralizadas

        for skill_path in paths:
            err = validate_skill_name(skill_path.name)
            if err:
                errors.append(f"{agent_name}/{skill_path.name}: {err}")

            err = validate_skill_path(skill_path)
            if err:
                errors.append(f"{agent_name}: {err}")

    return errors, warnings
