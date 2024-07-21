"""
Standalone script to download and setup multilspy code for use by the Tools Code
It clones the repo and sets up the appropriate symlink
"""

import git
import os
from argparse import ArgumentParser
import pathlib
import shutil

parser = ArgumentParser()
parser.add_argument('--force', action='store_true', help="Force clone multilspy")

if __name__ == '__main__':

    args = parser.parse_args()

    PROJECT_ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    MULTILSPY_INSTALL_DIR = os.path.join(PROJECT_ROOT_DIR, 'external/csharp/monitors4codegen')
    SYMLINK_PATH = os.path.join(os.path.dirname(__file__), 'monitors4codegen')

    if pathlib.Path(MULTILSPY_INSTALL_DIR).exists():
        print(f"WARNING: Target location for download ({MULTILSPY_INSTALL_DIR}) already exists ")
        if args.force is True:
            print(f"Deleting existing directory at {MULTILSPY_INSTALL_DIR}")
            shutil.rmtree(MULTILSPY_INSTALL_DIR)
        else:
            print("Exiting.")
            exit(0)

    print(f"Cloning multilspy fork into: {MULTILSPY_INSTALL_DIR}")
    git.Repo.clone_from('https://github.com/Shashank-Shet/monitors4codegen.git', MULTILSPY_INSTALL_DIR, branch='shashankshet/toolframework')

    if pathlib.Path(SYMLINK_PATH).exists():
        print(f"Removing existing symlink: {SYMLINK_PATH}")
        os.unlink(SYMLINK_PATH)

    SRC_PATH = os.path.join(MULTILSPY_INSTALL_DIR, 'src/monitors4codegen')
    print(f"Creating symlink from {SYMLINK_PATH} to {SRC_PATH}")
    os.symlink(SRC_PATH, SYMLINK_PATH)
