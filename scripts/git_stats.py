import statistics
import subprocess
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

total = sum(values)

print("Commits per day:", counts)
print("Total commits:", total)
print("Mean:", statistics.mean(values) if values else 0)
print("Std dev:", statistics.stdev(values) if len(values) > 1 else 0)
