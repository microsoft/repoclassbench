import os
import git
import sys
import gdown
import shutil
import logging
import pathlib
import zipfile
import subprocess
from argparse import ArgumentParser

parser = ArgumentParser()
parser.add_argument('--force', action='store_true')

FORCE_CLEAN_INSTALL = False
PROJECT_ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
DOTNET_ROOT_DIR  = os.path.join(PROJECT_ROOT_DIR, "external/csharp/dotnet_dir")
REPO_CONTAINER_DIR = os.path.join(PROJECT_ROOT_DIR, "temp/csharp/")

def setup_dotnet() -> None:
    # r = requests.get("https://dot.net/v1/dotnet-install.sh")
    # install_script_str = r.content.decode()
    # script_path = os.path.join(self.repo_container_dir, "dotnet-install.sh")
    # with open(script_path, "w") as f:
    #     f.write(install_script_str)
    os.makedirs(DOTNET_ROOT_DIR, exist_ok=True)
    dotnet_executable_path = os.path.join(DOTNET_ROOT_DIR, "dotnet")
    if FORCE_CLEAN_INSTALL is True:
        logging.warning(f"Removing existing dotnet installation at {DOTNET_ROOT_DIR}")
        shutil.rmtree(DOTNET_ROOT_DIR)
    if pathlib.Path(dotnet_executable_path).is_file():
        return
    tarball_url = "https://drive.google.com/uc?id=1JbiK1ScxS7Y6IkjZhJlbIk0VbXo7BN4k"
    logging.info("Downloading dotnet sdk")
    gdown.download(
        tarball_url,
        os.path.join(DOTNET_ROOT_DIR, "dotnet-sdk-8.0.301-linux-x64.tar.gz"),
        quiet=False,
    )
    logging.info("Download completed")
    try:
        subprocess.check_call(
            "tar -xzvf dotnet-sdk-8.0.301-linux-x64.tar.gz",
            shell=True,
            cwd=DOTNET_ROOT_DIR,
        )
    except subprocess.CalledProcessError as cpe:
        logging.error("ERROR: unable to extract dotnet sdk")
        logging.error(str(cpe))

def setup_multilspy():
    MULTILSPY_INSTALL_DIR = os.path.join(PROJECT_ROOT_DIR, 'external/csharp/monitors4codegen')
    SYMLINK_PATH = os.path.join(PROJECT_ROOT_DIR, 'repotools/csharp_tools/monitors4codegen')

    if FORCE_CLEAN_INSTALL is True and pathlib.Path(MULTILSPY_INSTALL_DIR).exists():
        logging.warning(f"Removing existing installation at: {str(pathlib.Path(MULTILSPY_INSTALL_DIR))}")
        shutil.rmtree(MULTILSPY_INSTALL_DIR)

    if not pathlib.Path(MULTILSPY_INSTALL_DIR).exists():

        logging.info(f"Cloning multilspy fork into: {MULTILSPY_INSTALL_DIR}")
        git.Repo.clone_from('https://github.com/Shashank-Shet/monitors4codegen.git', MULTILSPY_INSTALL_DIR, branch='shashankshet/toolframework')

        if pathlib.Path(SYMLINK_PATH).exists():
            logging.warning(f"Removing existing symlink: {SYMLINK_PATH}")
            os.unlink(SYMLINK_PATH)

        SRC_PATH = os.path.join(MULTILSPY_INSTALL_DIR, 'src/monitors4codegen')
        logging.info(f"Creating symlink from {SYMLINK_PATH} to {SRC_PATH}")
        os.symlink(SRC_PATH, SYMLINK_PATH)

        try:
            # This block is to trigger the download of OmniSharp
            EXP_DIR = os.path.join(REPO_CONTAINER_DIR, "original_repo/StabilityMatrix/")
            if not pathlib.Path(EXP_DIR).exists():
                download_data()
            from monitors4codegen.multilspy import SyncLanguageServer               # type: ignore
            from monitors4codegen.multilspy.multilspy_config import MultilspyConfig # type: ignore
            from monitors4codegen.multilspy.multilspy_logger import MultilspyLogger # type: ignore
            logger = MultilspyLogger(logging.INFO, logging.FileHandler("multilspy.log"))
            config = MultilspyConfig.from_dict({"code_language": 'csharp'})
            SLSP = SyncLanguageServer.create(config, logger, EXP_DIR)

        except Exception as e:
            logging.error("Unable to properly setup multilspy")
            logging.error(str(e))


def setup_env():
    logging.info("Setting up env vars")
    MULTILSPY_LIB_DIR = os.path.join(PROJECT_ROOT_DIR, 'external/csharp/monitors4codegen/src/')
    if MULTILSPY_LIB_DIR not in sys.path:
        sys.path.append(MULTILSPY_LIB_DIR)

    if DOTNET_ROOT_DIR not in os.environ['PATH']:
        os.environ['PATH'] += os.pathsep + DOTNET_ROOT_DIR

    if "DOTNET_ROOT" not in os.environ:
        os.environ['DOTNET_ROOT'] = DOTNET_ROOT_DIR

def download_data() -> None:
    original_repo_dir = os.path.join(REPO_CONTAINER_DIR, "original_repo")
    # If non-empty skip download
    if len(os.listdir(original_repo_dir)) > 0:
        return

    data_url = "https://drive.google.com/uc?id=1B1WM1G7E8Tcy3VpGPIgcKDB8w49zdtql"
    logging.info("Downloading dataset zip")
    gdown.download(
        data_url,
        os.path.join(REPO_CONTAINER_DIR, "csharp_repos.zip"),
        quiet=False,
    )
    logging.info("Download completed")
    with zipfile.ZipFile(
        os.path.join(REPO_CONTAINER_DIR, "csharp_repos.zip"), "r"
    ) as zip_ref:
        zip_ref.extractall(REPO_CONTAINER_DIR)
    extracted_folder_path = os.path.join(
        REPO_CONTAINER_DIR, "LLMTools_dataset"
    )
    os.rename(extracted_folder_path, original_repo_dir)
    # Below code creates a git index for each repo
    # So, for each task, after a change, we can revert back to the original state
    for dirpath in os.listdir(original_repo_dir):
        repo = git.Repo.init(os.path.join(original_repo_dir, dirpath))
        repo.index.add(repo.untracked_files)
        repo.index.commit("Initial commit")


if __name__ == '__main__':
    args = parser.parse_args()
    FORCE_CLEAN_INSTALL = args.force
    setup_dotnet()
    setup_multilspy()
else:
    setup_env()

