import os

KAGGLE_DATASETS = [
    "isuruprabath/brfss-2023-csv-dataset",
    "malaiarasugraj/global-health-statistics",
    "itachi9604/disease-symptom-description-dataset",
]


def download_kaggle(dataset):
    os.system(f"kaggle datasets download -d {dataset} -p data/ --unzip --force")


def main():
    os.makedirs("data", exist_ok=True)

    for kd in KAGGLE_DATASETS:
        download_kaggle(kd)


if __name__ == "__main__":
    main()
