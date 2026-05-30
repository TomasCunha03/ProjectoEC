"""
Git commit frequency statistics for the last 7 days.

Runs ``git log`` against the current repository and prints a per-day commit
count together with the total, mean, and standard deviation.  Useful for
quick team activity snapshots without leaving the terminal.
"""

import statistics
import subprocess
from collections import Counter

# Retrieve one date line per commit made in the last 7 days
cmd = [
    "git",
    "log",
    "--since=7 days ago",
    "--pretty=format:%ad",
    "--date=short",
]

# Each line is a YYYY-MM-DD date string; split produces one entry per commit
output = subprocess.check_output(cmd).decode().strip().split("\n")

# Count how many commits occurred on each distinct date
counts = Counter(output)

values = list(counts.values())

total = sum(values)

print("Commits per day:", counts)
print("Total commits:", total)
# Guard against empty history before calling statistics functions
print("Mean:", statistics.mean(values) if values else 0)
print("Std dev:", statistics.stdev(values) if len(values) > 1 else 0)
