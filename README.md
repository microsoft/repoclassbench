# Natural Language to Class-level Code Generation by Iterative Tool-augmented Reasoning over Repository

This repository contains the official code and data for the paper ["Natural Language to Class-level Code Generation by Iterative Tool-augmented Reasoning over Repository"](https://arxiv.org/abs/2405.01573), to be presented at the 2024 International Conference on Machine Learning Workshop on Data-Centric Machine Learning Research (DMLR workshop at ICML'24).

Our work introduces:
1. **RepoClassBench (RCB)**: A repository-level code-generation benchmark
2. **Retrieve-RepoTools-Reflect (RRR)**: A framework for code generation using Language Models (LLMs) with static-analysis tools in an agent setup

**Alternative title used for anonymity purposes:** Class-Level Code Generation from Natural Language Using Iterative, Tool-Enhanced Reasoning over Repository

## Abstract

LLMs have demonstrated significant potential in code generation tasks, achieving promising results at the function or statement level across various benchmarks. However, the complexities associated with creating code artifacts like classes, particularly within the context of real-world software repositories, remain underexplored. Prior research treats class-level generation as an isolated task, neglecting the intricate dependencies & interactions that characterize real-world software environments.

To address this gap, we introduce RepoClassBench, a comprehensive benchmark designed to rigorously evaluate LLMs in generating complex, class-level code within real-world repositories. RepoClassBench includes "Natural Language to Class generation" tasks across Java, Python & C# from a selection of repositories. We ensure that each class in our dataset not only has cross-file dependencies within the repository but also includes corresponding test cases to verify its functionality. We find that current models struggle with the realistic challenges posed by our benchmark, primarily due to their limited exposure to relevant repository contexts.

To address this shortcoming, we introduce Retrieve-Repotools-Reflect (RRR), a novel approach that equips LLMs with static analysis tools to iteratively navigate & reason about repository-level context in an agent-based framework. Our experiments demonstrate that RRR significantly outperforms existing baselines on RepoClassBench, showcasing its effectiveness across programming languages & under various settings. Our findings emphasize the critical need for code-generation benchmarks to incorporate repo-level dependencies to more accurately reflect the complexities of software development.

Our work shows the benefits of leveraging specialized tools to enhance LLMs' understanding of repository context. 


## Repository Contents
* `data`: Contains the RepoClassBench dataset contents and the metadata to initialize the evaluation harness pipeline. [More details here](#Dataset-Contents).
* `repoclassbench`: Contains the code to initialize the repository environments for Java, C# and Python; to take a piece of class code and measure its correctness with respect to the testcases in the repository. [More details here](#Using-the-benchmark).
* `repotools`: Contains the implementation of static-analysis tools used by the agentic-framework in our work to reason about the repository.
* `rrr`: Code for the RRR agent interacting with the evaluation harness to solve benchmark tasks
* `project_utils`: Common utility functions used across the project

## Dataset Contents

### Dataset Statistics

| Language | Number of Tasks |
|----------|:---------------:|
| Java     |      130        |
| Python   |       97        |
| C#       |       60        |

### Benchmark Attributes

The benchmark data is located in `data/input`, with separate files for Python, Java, and C#. Each file contains the following attributes for each task:

1. `task_id`: Unique identifier for each task in the benchmark.
2. `class_name`: Name of the class being tested.
3. `file_name`: Path to the file containing the ground truth implementation of the class within the repository.
4. `detailed_description`: Verbose description of the class, used by the agent/LLM to generate code.
5. `sketchy_description`: Less detailed description of the class, providing an alternative prompt for code generation.
6. `repo_metadata`: Information about the repository containing the class, including:
   - `repo_name`
   - `commit_id`
   - Other fields necessary for cloning the repository, checking out the relevant commit, and setting up the environment for building/executing tests.
7. `evaluation_metadata`: Data for assessing the correctness of generated code:
   - For Java: Includes the test class used to validate the implementation.
   - For Python: Lists the pytest names expected to change from FAILED to PASSED when the correct class implementation is added to the repository.
8. `ground_truth_class_body`: The correct implementation of the class being tested.


## Getting Started

### Setting up the Project Repository

To get started with the project, follow these steps:

1. Clone the repository to your local machine:
```bash
git clone https://github.com/microsoft/repoclassbench
cd repoclassbench
```

2. Create and activate the conda environment:
```bash
conda create --name repoclassbench_env python=3.11
conda activate repoclassbench_env
```
3. Install the required dependencies
```bash
pip install -r requirements.txt
```

## Using the benchmark
### Ensuring the evaluation harness is properly setup
Before evaluating your pipeline/setup, verify that the required environments and repositories in the evaluation harness are properly set up. If not, the ground truth implementation of one or more tasks across the three languages may fail. Run the following tests to ensure proper setup:

```bash
# To ensure harness is setup for C#
pytest -x repoclassbench/tests/test_csharp.py

# To ensure harness is setup for Java
pytest -x repoclassbench/tests/test_java.py

# To ensure harness is setup for Python
pytest -x repoclassbench/tests/test_python.py
```



### Testing your approach on the benchmark
If you're ready to see how your code generation approach stacks up against our benchmark, you'll find sample code to help you get started in the `repoclassbench/tests` directory. Follow this step-by-step guide to test your code on a specific task:

#### Step 1: Initialize the Dataset
Start by creating a `Dataset` object for the programming language you're working with. For example, if you're testing Python code, you would write:

```python
from repoclassbench.dataset import Dataset

# Initialize the dataset for Python with detailed specifications
dataset = Dataset(language="python", specification="detailed", delete_relatives=False)
```

#### Step 2: Select a Task
Next, choose a task from the dataset to test your code on. You can do this by fetching the `task` object using its unique identifier (`task_id`):

```python
# Replace 'task_id' with the actual ID of the task you want to test
task = dataset.get_instance_and_setup_env(task_id)
```

#### Step 3: Prepare for Evaluation
Retrieve the evaluation tools for the task. This will give you a `TaskData` object, which includes the evaluator, a description of the class you need to generate, and the location of the relevant code repository.

```python
# Get the evaluator from the task object
evaluator = task.evaluator

# The path to the repository files and the class description are also available
repository_path = task.repo_dir
description_to_use = task.description
```

#### Step 4: Run the Evaluation
Finally, it's time to see how your generated code performs. Use the evaluator to test your code and print out the results.

```python
# 'code_test' should be replaced with the class code generated by your approach
evaluation_results = evaluator.evaluate(code_test)

# Display the outcome of the evaluation
print("Number of passed testcases: ", evaluation_results.passed_tests)
print("Number of failed testcases: ", evaluation_results.failed_tests)
print("Did the code compile/pass linter checks: ", evaluation_results.compile_status)
print("Error feedback from the harness: ", evaluation_results.error_feedback)
```

Remember to replace `code_test` with the actual code generated by your approach. The evaluator will run your code against the test cases and provide feedback on how many tests passed, how many failed, whether the code compiled successfully, and any errors that were encountered.



## Citation
Please consider citing the following paper when using our code and benchmark.

```
@misc{deshpande2024classlevelcodegenerationnatural,
      title={Class-Level Code Generation from Natural Language Using Iterative, Tool-Enhanced Reasoning over Repository}, 
      author={Ajinkya Deshpande and Anmol Agarwal and Shashank Shet and Arun Iyer and Aditya Kanade and Ramakrishna Bairi and Suresh Parthasarathy},
      year={2024},
      eprint={2405.01573},
      archivePrefix={arXiv},
      primaryClass={cs.SE},
      url={https://arxiv.org/abs/2405.01573}, 
}
```


## Contributing

This project welcomes contributions and suggestions.  Most contributions require you to agree to a Contributor License Agreement (CLA) declaring that you have the right to, and actually do, grant us the rights to use your contribution. For details, visit https://cla.opensource.microsoft.com.

When you submit a pull request, a CLA bot will automatically determine whether you need to provide a CLA and decorate the PR appropriately (e.g., status check, comment). Simply follow the instructions provided by the bot. You will only need to do this once across all repos using our CLA.

This project has adopted the [Microsoft Open Source Code of Conduct](https://opensource.microsoft.com/codeofconduct/). For more information see the [Code of Conduct FAQ](https://opensource.microsoft.com/codeofconduct/faq/) or contact [opencode@microsoft.com](mailto:opencode@microsoft.com) with any additional questions or comments.

## Trademarks

This project may contain trademarks or logos for projects, products, or services. Authorized use of Microsoft trademarks or logos is subject to and must follow [Microsoft's Trademark & Brand Guidelines](https://www.microsoft.com/en-us/legal/intellectualproperty/trademarks/usage/general). Use of Microsoft trademarks or logos in modified versions of this project must not cause confusion or imply Microsoft sponsorship. Any use of third-party trademarks or logos are subject to those third-party's policies.
