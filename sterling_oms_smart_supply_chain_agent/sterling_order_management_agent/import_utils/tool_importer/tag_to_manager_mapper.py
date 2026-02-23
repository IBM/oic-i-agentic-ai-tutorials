"""Bash helper to find paths, Should be ran with native python."""

from collections import defaultdict
from pathlib import Path
from typing import Dict, List

from import_utils.utils.directory import find_target_directory
from tabulate import tabulate


class TagToManagerMapper:
    """Determine if tag or path, if tag find the path to the manager yaml."""

    agent_yaml_parent_dir: Path
    tag_to_manager_mapping: Dict[str, Path] = dict()
    tags_with_collisions: Dict[str, List[Path]] = dict()

    def __init__(self) -> None:
        self.agent_yaml_parent_dir = find_target_directory("collaborator_agents")
        assert self.agent_yaml_parent_dir.exists()
        self._build_manager_tags_mapping()

    def _build_manager_tags_mapping(self) -> None:
        """
        Dynamically scan the collaborator yamls and build domain.manager_name tags to easily call in
        import.

        Sort out tags that are valid and tags that have collisions into separate data objects.
        """

        tag_to_manager_mapping = defaultdict(set)
        for root, _, files in self.agent_yaml_parent_dir.walk():
            for file in files:
                file_name = str(Path(file).with_suffix(""))

                # Look for yaml paths that end in "_manager.yaml"
                if str(file).endswith(".yaml") and file_name.endswith("_manager"):
                    rel_path = Path(root / file).relative_to(self.agent_yaml_parent_dir)
                    abs_path = root / file
                    assert abs_path.exists(), f"Sanity check failed, path doesn't exist: {abs_path}"

                    # Build Callable Tag
                    domain_tag = rel_path.parts[0]
                    manager_tag = rel_path.with_suffix("").parts[-1]
                    callable_tag = f"{domain_tag}.{manager_tag}"

                    tag_to_manager_mapping[callable_tag].add(abs_path)

        self.tags_with_collisions = {
            tag: list(tag_to_manager_mapping[tag])
            for tag, loc in tag_to_manager_mapping.items()
            if len(loc) > 1
        }

        self.tag_to_manager_mapping = {
            tag: next(iter(path_set))
            for tag, path_set in tag_to_manager_mapping.items()
            if len(path_set) == 1
        }

    def get_manager_path_from_tag(self, path_or_tag: str) -> Path:
        """
        Use Mapper to fetch the path using tag as a key. If name collisions are found, just print a
        warning, but will still continue with import if tag used doesn't have collisions.

        Args:
            path_or_tag: path or tag, if tag pull path from map

        Returns:
            Path obj to manager agents yaml
        :raise: KeyError if the tag used has a name collision.
        """
        # TODO: use a logger for this message.
        # Print out warnings if `any` collisions are found.
        for dup_tag, path_list in self.tags_with_collisions.items():
            print(f"[WARN] Collisions Found: {dup_tag} -> {", ".join([str(p) for p in path_list])}")

        # Raise error if target tag has collisions
        if path_or_tag in self.tags_with_collisions:
            raise KeyError(
                f"Collisions Found: {path_or_tag} -> {", ".join([str(p) for p in self.tags_with_collisions[path_or_tag]])}"
            )

        if path_or_tag in self.tag_to_manager_mapping:
            return (
                self.tag_to_manager_mapping[path_or_tag]
                .relative_to(self.agent_yaml_parent_dir.parent)
                .resolve()
            )
        return Path(path_or_tag)

    def print_supported_manager_tags(self) -> None:
        """Print a formatted list of supported manager tags and paths for developers to
        reference."""

        columns = ["Manager Tag", "Location"]
        table = []

        # Add valid tags and paths to table
        for manager_tag, manager_path in self.tag_to_manager_mapping.items():
            table.append(
                [
                    manager_tag,
                    str(manager_path.relative_to(self.agent_yaml_parent_dir.parent)),
                ]
            )

        # Add tags with collisions to the bottom of the table with all paths referenced to tag
        for manager_tag, manager_paths in self.tags_with_collisions.items():
            table.append(
                [
                    manager_tag + " (Disabled: Collision)",
                    "\n".join(
                        [
                            str(manager_path.relative_to(self.agent_yaml_parent_dir.parent))
                            for manager_path in manager_paths
                        ]
                    ),
                ]
            )

        print("\n" + tabulate(table, headers=columns))
