#!/usr/bin/env python3
"""
Checkpoint Manager - Save and restore code states
Manages git stash-based checkpoints for easy rollback
"""

import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional


class CheckpointManager:
    """Manages code checkpoints using git stash."""

    def __init__(self, prefix: str = "claude-checkpoint"):
        """Initialize checkpoint manager."""
        self.prefix = prefix
        self._verify_git_repo()

    def _verify_git_repo(self) -> None:
        """Verify we're in a git repository."""
        try:
            subprocess.run(
                ["git", "rev-parse", "--git-dir"],
                check=True,
                capture_output=True,
            )
        except subprocess.CalledProcessError:
            print("Error: Not in a git repository", file=sys.stderr)
            sys.exit(1)

    def create(self, message: Optional[str] = None) -> str:
        """Create a new checkpoint."""
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        checkpoint_msg = f"{self.prefix}: {timestamp}"
        if message:
            checkpoint_msg += f" - {message}"

        try:
            # Stash all changes including untracked files
            result = subprocess.run(
                ["git", "stash", "push", "-u", "-m", checkpoint_msg],
                check=True,
                capture_output=True,
                text=True,
            )

            print(f"✅ Checkpoint created: {checkpoint_msg}")

            # Immediately pop to restore working state
            subprocess.run(
                ["git", "stash", "apply", "stash@{0}"],
                check=True,
                capture_output=True,
            )

            return checkpoint_msg

        except subprocess.CalledProcessError as e:
            print(f"Error creating checkpoint: {e.stderr}", file=sys.stderr)
            sys.exit(1)

    def list(self) -> List[dict]:
        """List all checkpoints."""
        try:
            result = subprocess.run(
                ["git", "stash", "list"],
                check=True,
                capture_output=True,
                text=True,
            )

            checkpoints = []
            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue

                if self.prefix in line:
                    # Parse: stash@{0}: On branch: claude-checkpoint: 2025-10-01_...
                    parts = line.split(": ", 2)
                    if len(parts) >= 3:
                        stash_ref = parts[0]
                        message = parts[2]
                        checkpoints.append({"ref": stash_ref, "message": message})

            return checkpoints

        except subprocess.CalledProcessError as e:
            print(f"Error listing checkpoints: {e.stderr}", file=sys.stderr)
            return []

    def restore(self, stash_ref: str) -> None:
        """Restore a checkpoint by stash reference."""
        try:
            # Show what will be restored
            print(f"Restoring checkpoint: {stash_ref}")

            # Apply the stash
            subprocess.run(
                ["git", "stash", "apply", stash_ref],
                check=True,
            )

            print(f"✅ Checkpoint restored: {stash_ref}")

        except subprocess.CalledProcessError as e:
            print(f"Error restoring checkpoint: {e}", file=sys.stderr)
            sys.exit(1)

    def delete(self, stash_ref: str) -> None:
        """Delete a specific checkpoint."""
        try:
            subprocess.run(
                ["git", "stash", "drop", stash_ref],
                check=True,
                capture_output=True,
            )

            print(f"✅ Checkpoint deleted: {stash_ref}")

        except subprocess.CalledProcessError as e:
            print(f"Error deleting checkpoint: {e.stderr}", file=sys.stderr)
            sys.exit(1)

    def clean(self, keep_latest: int = 5) -> None:
        """Clean old checkpoints, keeping only the latest N."""
        checkpoints = self.list()

        if len(checkpoints) <= keep_latest:
            print(f"Only {len(checkpoints)} checkpoints, nothing to clean")
            return

        to_delete = checkpoints[keep_latest:]

        print(f"Deleting {len(to_delete)} old checkpoints...")

        for checkpoint in to_delete:
            self.delete(checkpoint["ref"])

        print(f"✅ Kept {keep_latest} latest checkpoints")


def main() -> None:
    """CLI interface for checkpoint manager."""
    import argparse

    parser = argparse.ArgumentParser(description="Manage code checkpoints")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Create checkpoint
    create_parser = subparsers.add_parser("create", help="Create a new checkpoint")
    create_parser.add_argument(
        "-m", "--message", help="Checkpoint message", default=None
    )

    # List checkpoints
    subparsers.add_parser("list", help="List all checkpoints")

    # Restore checkpoint
    restore_parser = subparsers.add_parser("restore", help="Restore a checkpoint")
    restore_parser.add_argument("ref", help="Stash reference (e.g., stash@{0})")

    # Delete checkpoint
    delete_parser = subparsers.add_parser("delete", help="Delete a checkpoint")
    delete_parser.add_argument("ref", help="Stash reference (e.g., stash@{0})")

    # Clean old checkpoints
    clean_parser = subparsers.add_parser("clean", help="Clean old checkpoints")
    clean_parser.add_argument(
        "-k",
        "--keep",
        type=int,
        default=5,
        help="Number of checkpoints to keep (default: 5)",
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    manager = CheckpointManager()

    if args.command == "create":
        manager.create(args.message)
    elif args.command == "list":
        checkpoints = manager.list()
        if not checkpoints:
            print("No checkpoints found")
        else:
            print("\nCheckpoints:")
            for cp in checkpoints:
                print(f"  {cp['ref']}: {cp['message']}")
    elif args.command == "restore":
        manager.restore(args.ref)
    elif args.command == "delete":
        manager.delete(args.ref)
    elif args.command == "clean":
        manager.clean(args.keep)


if __name__ == "__main__":
    main()
