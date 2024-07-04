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
