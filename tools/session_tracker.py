#!/usr/bin/env python3
"""
Session Tracker - Track Claude Code sessions and changes
Records what files were modified, decisions made, and changes implemented
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


class SessionTracker:
    """Tracks Claude Code sessions and changes."""

    def __init__(self, sessions_file: str = ".claude/sessions.jsonl"):
        """Initialize session tracker."""
        self.sessions_file = Path(sessions_file)
        self.sessions_file.parent.mkdir(parents=True, exist_ok=True)

    def start_session(self, description: Optional[str] = None) -> str:
        """Start a new session."""
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S")

        session = {
            "session_id": session_id,
            "start_time": datetime.now().isoformat(),
            "description": description or "New Claude Code session",
            "files_modified": [],
            "decisions": [],
            "status": "active",
        }

        self._append_session(session)

        print(f"✅ Started session: {session_id}")
        if description:
            print(f"   Description: {description}")

        return session_id

    def end_session(self, session_id: str, summary: Optional[str] = None) -> None:
        """End a session."""
        sessions = self._load_sessions()

        for session in sessions:
            if session["session_id"] == session_id:
                session["end_time"] = datetime.now().isoformat()
                session["status"] = "completed"
                if summary:
                    session["summary"] = summary

                self._save_sessions(sessions)

                print(f"✅ Ended session: {session_id}")
                if summary:
                    print(f"   Summary: {summary}")

                return

        print(f"Error: Session {session_id} not found", file=sys.stderr)

    def add_file(self, session_id: str, file_path: str, action: str) -> None:
        """Add a file modification to session."""
        sessions = self._load_sessions()

        for session in sessions:
            if session["session_id"] == session_id:
                file_entry = {
                    "file": file_path,
                    "action": action,
                    "timestamp": datetime.now().isoformat(),
                }

                session["files_modified"].append(file_entry)

                self._save_sessions(sessions)
                print(f"📝 Tracked: {action} {file_path}")
                return

        print(f"Error: Session {session_id} not found", file=sys.stderr)

    def add_decision(
        self, session_id: str, decision: str, rationale: Optional[str] = None
    ) -> None:
        """Add a decision to session."""
        sessions = self._load_sessions()

        for session in sessions:
            if session["session_id"] == session_id:
                decision_entry = {
                    "decision": decision,
                    "rationale": rationale,
                    "timestamp": datetime.now().isoformat(),
                }

                session["decisions"].append(decision_entry)

                self._save_sessions(sessions)
                print(f"💡 Decision tracked: {decision}")
                if rationale:
                    print(f"   Rationale: {rationale}")
                return

        print(f"Error: Session {session_id} not found", file=sys.stderr)

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific session."""
        sessions = self._load_sessions()

        for session in sessions:
            if session["session_id"] == session_id:
                return session

        return None

    def list_sessions(self, limit: int = 10) -> List[Dict[str, Any]]:
        """List recent sessions."""
        sessions = self._load_sessions()
        return sessions[-limit:][::-1]  # Most recent first

    def _append_session(self, session: Dict[str, Any]) -> None:
        """Append a session to the JSONL file."""
        with open(self.sessions_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(session) + "\n")

    def _load_sessions(self) -> List[Dict[str, Any]]:
        """Load all sessions from JSONL file."""
        if not self.sessions_file.exists():
            return []

        sessions = []

        with open(self.sessions_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    sessions.append(json.loads(line))

        return sessions

    def _save_sessions(self, sessions: List[Dict[str, Any]]) -> None:
        """Save all sessions to JSONL file."""
        with open(self.sessions_file, "w", encoding="utf-8") as f:
            for session in sessions:
                f.write(json.dumps(session) + "\n")

    def print_session(self, session: Dict[str, Any]) -> None:
        """Print session details."""
        print(f"\n📊 Session: {session['session_id']}")
        print(f"   Status: {session['status']}")
        print(f"   Started: {session['start_time']}")

        if "end_time" in session:
            print(f"   Ended: {session['end_time']}")

        if "description" in session:
            print(f"   Description: {session['description']}")

        if session.get("files_modified"):
            print(f"\n   Files Modified ({len(session['files_modified'])}):")
            for file_entry in session["files_modified"]:
                print(f"      {file_entry['action']}: {file_entry['file']}")

        if session.get("decisions"):
            print(f"\n   Decisions ({len(session['decisions'])}):")
            for decision in session["decisions"]:
                print(f"      - {decision['decision']}")
                if decision.get("rationale"):
                    print(f"        Rationale: {decision['rationale']}")

        if "summary" in session:
            print(f"\n   Summary: {session['summary']}")

        print()


def main() -> None:
    """CLI interface for session tracker."""
    import argparse

    parser = argparse.ArgumentParser(description="Track Claude Code sessions")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Start session
    start_parser = subparsers.add_parser("start", help="Start a new session")
    start_parser.add_argument("-d", "--description", help="Session description")

    # End session
    end_parser = subparsers.add_parser("end", help="End a session")
    end_parser.add_argument("session_id", help="Session ID")
    end_parser.add_argument("-s", "--summary", help="Session summary")

    # Add file
    file_parser = subparsers.add_parser("file", help="Add file modification")
    file_parser.add_argument("session_id", help="Session ID")
    file_parser.add_argument("file_path", help="File path")
    file_parser.add_argument("action", help="Action (created/modified/deleted)")

    # Add decision
    decision_parser = subparsers.add_parser("decision", help="Add decision")
    decision_parser.add_argument("session_id", help="Session ID")
    decision_parser.add_argument("decision", help="Decision made")
    decision_parser.add_argument("-r", "--rationale", help="Rationale")

    # Show session
    show_parser = subparsers.add_parser("show", help="Show session details")
    show_parser.add_argument("session_id", help="Session ID")

    # List sessions
    list_parser = subparsers.add_parser("list", help="List recent sessions")
    list_parser.add_argument(
        "-n", "--limit", type=int, default=10, help="Number of sessions to show"
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    tracker = SessionTracker()

    if args.command == "start":
        tracker.start_session(args.description)
    elif args.command == "end":
        tracker.end_session(args.session_id, args.summary)
    elif args.command == "file":
        tracker.add_file(args.session_id, args.file_path, args.action)
    elif args.command == "decision":
        tracker.add_decision(args.session_id, args.decision, args.rationale)
    elif args.command == "show":
        session = tracker.get_session(args.session_id)
        if session:
            tracker.print_session(session)
        else:
            print(f"Error: Session {args.session_id} not found", file=sys.stderr)
    elif args.command == "list":
        sessions = tracker.list_sessions(args.limit)
        if not sessions:
            print("No sessions found")
        else:
            print("\nRecent Sessions:")
            for session in sessions:
                status_icon = "✅" if session["status"] == "completed" else "🔄"
                print(
                    f"  {status_icon} {session['session_id']}: {session.get('description', 'No description')}"
                )
                print(f"      Files: {len(session.get('files_modified', []))}, "
                      f"Decisions: {len(session.get('decisions', []))}")


if __name__ == "__main__":
    main()
