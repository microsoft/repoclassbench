import os
import git
import sys
import gdown
import shutil
import pathlib
import subprocess
from argparse import ArgumentParser

parser = ArgumentParser()
parser.add_argument('--force', action='store_true')

FORCE_CLEAN_INSTALL = False
PROJECT_ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
DOTNET_ROOT_DIR  = os.path.join(PROJECT_ROOT_DIR, "external/csharp/dotnet_dir")

def setup_dotnet() -> None:
    # r = requests.get("https://dot.net/v1/dotnet-install.sh")
    # install_script_str = r.content.decode()
    # script_path = os.path.join(self.repo_container_dir, "dotnet-install.sh")
    # with open(script_path, "w") as f:
    #     f.write(install_script_str)
    os.makedirs(DOTNET_ROOT_DIR, exist_ok=True)
    dotnet_executable_path = os.path.join(DOTNET_ROOT_DIR, "dotnet")
    if FORCE_CLEAN_INSTALL is True:
        print(f"Removing existing dotnet installation at {DOTNET_ROOT_DIR}")
        shutil.rmtree(DOTNET_ROOT_DIR)
    if pathlib.Path(dotnet_executable_path).is_file():
        return
    tarball_url = "https://drive.google.com/uc?id=1JbiK1ScxS7Y6IkjZhJlbIk0VbXo7BN4k"
    gdown.download(
        tarball_url,
        os.path.join(DOTNET_ROOT_DIR, "dotnet-sdk-8.0.301-linux-x64.tar.gz"),
        quiet=False,
    )
    try:
        subprocess.check_call(
            "tar -xzvf dotnet-sdk-8.0.301-linux-x64.tar.gz",
            shell=True,
            cwd=DOTNET_ROOT_DIR,
        )
    except subprocess.CalledProcessError as cpe:
        print("ERROR: unable to extract dotnet sdk")
        print(str(cpe))

def setup_multilspy():
    MULTILSPY_INSTALL_DIR = os.path.join(PROJECT_ROOT_DIR, 'external/csharp/monitors4codegen')
    SYMLINK_PATH = os.path.join(PROJECT_ROOT_DIR, 'repotools/csharp_tools/monitors4codegen')

    if DOTNET_ROOT_DIR not in os.environ['PATH']:
        os.environ['PATH'] += os.pathsep + DOTNET_ROOT_DIR
    if "DOTNET_ROOT" not in os.environ:
        os.environ['DOTNET_ROOT'] = DOTNET_ROOT_DIR

    if FORCE_CLEAN_INSTALL is True and pathlib.Path(MULTILSPY_INSTALL_DIR).exists():
        print(f"Removing existing installation at: {str(pathlib.Path(MULTILSPY_INSTALL_DIR))}")
        shutil.rmtree(MULTILSPY_INSTALL_DIR)

    if not pathlib.Path(MULTILSPY_INSTALL_DIR).exists():

        print(f"Cloning multilspy fork into: {MULTILSPY_INSTALL_DIR}")
        git.Repo.clone_from('https://github.com/Shashank-Shet/monitors4codegen.git', MULTILSPY_INSTALL_DIR, branch='shashankshet/toolframework')

        if pathlib.Path(SYMLINK_PATH).exists():
            print(f"Removing existing symlink: {SYMLINK_PATH}")
            os.unlink(SYMLINK_PATH)

        SRC_PATH = os.path.join(MULTILSPY_INSTALL_DIR, 'src/monitors4codegen')
        print(f"Creating symlink from {SYMLINK_PATH} to {SRC_PATH}")
        os.symlink(SRC_PATH, SYMLINK_PATH)

def setup_env():
    MULTILSPY_LIB_DIR = os.path.join(PROJECT_ROOT_DIR, 'external/csharp/monitors4codegen/src/')
    if MULTILSPY_LIB_DIR not in sys.path:
        sys.path.append(MULTILSPY_LIB_DIR)

    if DOTNET_ROOT_DIR not in os.environ['PATH']:
        os.environ['PATH'] += os.pathsep + DOTNET_ROOT_DIR

if __name__ == '__main__':
    args = parser.parse_args()
    FORCE_CLEAN_INSTALL = args.force
    setup_dotnet()
    setup_multilspy()
else:
    setup_env()

