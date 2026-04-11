import subprocess
import statistics
from collections import Counter

cmd = [
    "git",
    "log",
    "--since=7 days ago",
    "--pretty=format:%ad",
    "--date=short",
]

output = subprocess.check_output(cmd).decode().strip().split("\n")

counts = Counter(output)

values = list(counts.values())

print("Commits per day:", counts)
print("Mean:", statistics.mean(values))
print("Std dev:", statistics.stdev(values) if len(values) > 1 else 0)