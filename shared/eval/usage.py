"""Append-only CSV usage log (tokens, cost, latency per run). Task-agnostic."""
import csv
import os


class UsageLog:
    def __init__(self, path: str, fields: list[str]):
        self.path, self.fields = path, fields
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        if not os.path.exists(path):
            with open(path, "w", newline="") as f:
                csv.DictWriter(f, fieldnames=fields).writeheader()

    def append(self, row: dict) -> None:
        with open(self.path, "a", newline="") as f:
            csv.DictWriter(f, fieldnames=self.fields, extrasaction="ignore").writerow(row)
