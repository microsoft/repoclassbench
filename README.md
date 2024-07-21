# RepoClassBench & RRR

This repository contains the code and data for our paper on RepoClassBench and Retrieve-Repotools-Reflect (RRR), a novel approach to enhance Language Learning Models (LLMs) understanding of repository context for code generation tasks.

## Prerequisites

- Python 3.11

## Getting Started

To get started with the project, clone the repository to your local machine:

```bash
git clone https://github.com/your_username_/Project-Name.git
```

## Contents

The repository contains the following:

- `repoclassbench`: This is the comprehensive benchmark designed to rigorously evaluate LLMs in generating complex, class-level code within real-world repositories.

- `repotools`: These are the static analysis tools that are used by the RRR approach to navigate and reason about repository-level context.

- `rrr`: This is the implementation of our novel Retrieve-Repotools-Reflect (RRR) approach that equips LLMs with the ability to iteratively navigate and reason about repository-level context in an agent-based framework.

## About the Paper

LLMs have demonstrated significant potential in code generation tasks, achieving promising results at the function or statement level across various benchmarks. However, the complexities associated with creating code artifacts like classes, particularly within the context of real-world software repositories, remain underexplored.

To address this gap, we introduce RepoClassBench, a comprehensive benchmark designed to rigorously evaluate LLMs in generating complex, class-level code within real-world repositories. RepoClassBench includes "Natural Language to Class generation" tasks across Java, Python & C# from a selection of repositories.

We find that current models struggle with the realistic challenges posed by our benchmark, primarily due to their limited exposure to relevant repository contexts. To address this shortcoming, we introduce Retrieve-Repotools-Reflect (RRR), a novel approach that equips LLMs with static analysis tools to iteratively navigate & reason about repository-level context in an agent-based framework.

Our experiments demonstrate that RRR significantly outperforms existing baselines on RepoClassBench, showcasing its effectiveness across programming languages & under various settings. Our findings emphasize the critical need for code-generation benchmarks to incorporate repo-level dependencies to more accurately reflect the complexities of software development.

Our work shows the benefits of leveraging specialized tools to enhance LLMs' understanding of repository context. We plan to make our dataset & evaluation harness public.

# TODOs
* For all of us, giving a task ID for all the tasks in our respective datasets
* Script to create temp/java: Ajinkya

```bash
while read -r env; do
    conda env remove -n "$env" -y
done <<< "$(conda env list | grep -E 'litestar-org__litestar-0001|psf__requests-6028|pvlib__pvlib-python-1854|pydata__xarray-7444|pydicom__pydicom-1720|pylint-dev__astroid-2309|pylint-dev__pylint-4858|pylint-dev__pylint-8929|pytest-dev__pytest-10624|pyvista__pyvista-4853|scikit-learn__scikit-learn-26644' | awk '{print $1}')"

```

# Attributes needed in the dataset
* `task_id`
* `class_name`
* `file`
* `detailed_description`
* `sketchy_description`
* `repo_metadata`
* `evaluation_metadata`
* `ground_truth_class_body`


## Python tests
```bash
pytest -x repoclassbench/tests/test_python.py
python -m  repotools.python_tools.__init__

```