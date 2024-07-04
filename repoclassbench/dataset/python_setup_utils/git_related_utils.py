import os
from git import Repo, GitCommandError
from repoclassbench.common_utils import fetch_ist_adjusted_logger


logger = fetch_ist_adjusted_logger()


def reset_to_commit(repo_path: str, commit_id: str):
    """
    Reset the repository to a specific commit without affecting .gitignore files.

    Args:
        repo_path (str): Path to the repository.
        commit_id (str): The commit ID to reset to.

    Returns:
        bool: True if reset was successful, False otherwise.
    """
    try:
        # Initialize the repository object
        repo = Repo(repo_path)

        # Ensure the repo is not bare and the commit_id exists
        if repo.bare:
            logger.error("Cannot reset a bare repository.")
            return False

        # Check if the commit_id exists in the repository
        if commit_id not in repo.git.rev_list("--all"):
            logger.error(f"Commit ID {commit_id} does not exist in the repository.")
            return False

        # Perform a hard reset to the specified commit
        repo.git.reset("--hard", commit_id)
        logger.info(f"Repository has been successfully reset to commit {commit_id}.")
        return True
    except Exception as e:
        logger.exception(f"An error occurred while resetting the repository: {e}")
        return False
