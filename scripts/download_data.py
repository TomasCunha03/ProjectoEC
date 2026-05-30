"""
Kaggle dataset downloader.

Downloads all datasets listed in KAGGLE_DATASETS into the local data/
directory using the Kaggle CLI.  Requires KAGGLE_USERNAME and KAGGLE_KEY
environment variables (or a ~/.kaggle/kaggle.json credentials file) to
be configured before running.
"""

import os

# Kaggle dataset slugs (<owner>/<dataset-name>) to download
KAGGLE_DATASETS = [
    "isuruprabath/brfss-2023-csv-dataset",
    "malaiarasugraj/global-health-statistics",
    "itachi9604/disease-symptom-description-dataset",
]


def download_kaggle(dataset):
    """Download and unzip a single Kaggle dataset into data/.

    Uses --force so that an existing download is always refreshed.

    Args:
        dataset: Kaggle dataset identifier in the form ``owner/dataset-name``.
    """
    os.system(f"kaggle datasets download -d {dataset} -p data/ --unzip --force")


def main():
    """Ensure the data directory exists, then download every listed dataset."""
    os.makedirs("data", exist_ok=True)

    for kd in KAGGLE_DATASETS:
        download_kaggle(kd)


if __name__ == "__main__":
    main()
