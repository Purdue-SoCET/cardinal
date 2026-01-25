# SoCET GPU Contributing Guide - WORK IN PROGRESS

> **Note:** This is a work in progress. Any feedback is greatly appreciated. Message Seth McConkey (@s3f2607) on Discord

## Directory Structure (Work In Progress)
> **Note:** Do not edit this structure directly. Edit the [directory structure source file](./dir_structure_source.md) and use [this website](https://tree.nathanfriend.com) to render it into the format below
```
cardinal/
└── gpu/
    ├── common/
    │   ├── custom_enums_multi.py
    │   └── custom_enums.py
    ├── emulator/
    │   └── <emulator_files>
    ├── simulator/
    │   └── src/
    │       ├── schedule/
    │       │   ├── stage.py
    │       │   └── <file_name>.py
    │       ├── fetch/
    │       │   ├── stage.py
    │       │   └── <file_name>.py
    │       ├── decode/
    │       │   ├── stage.py
    │       │   └── <file_name>.py
    │       ├── issue/
    │       │   ├── stage.py
    │       │   └── <file_name>.py
    │       ├── execute/
    │       │   ├── stage.py
    │       │   ├── arithmetic_functional_unit.py
    │       │   └── functional_sub_unit.py
    │       ├── writeback/
    │       │   ├── stage.py
    │       │   └── writeback_buffer.py
    │       ├── memory/
    │       │   ├── memory.py
    │       │   ├── dcache.py
    │       │   ├── icache.py
    │       │   └── <file_name>.py
    │       ├── utils/
    │       │   ├── performance_counter.py
    │       │   └── <file_name>.py
    │       └── <name_of_file_used_in_multiple_stages>.py
    ├── tests/
    │   ├── common/
    │   │   ├── assembly/
    │   │   │   └── <assembly_test_for_both_sim_and_em>.asm
    │   │   └── benchmark/
    │   │       └── <benchmark_tests>
    │   ├── emulator/
    │   │   └── <emulator_tests>
    │   └── simulator/
    │       ├── frontend/
    │       │   ├── schedule/
    │       │   │   └── <name_of_scheduling_unit_test>.py
    │       │   ├── fetch/
    │       │   │   └── <name_of_fetch_unit_test>.py
    │       │   ├── decode/
    │       │   │   └── <name_of_decode_unit_test>.py
    │       │   ├── issue/
    │       │   │   └── <name_of_issue_unit_test>.py
    │       │   └── <name_of_frontend_unit_test>.py
    │       ├── backend/
    │       │   ├── execute/
    │       │   │   └── <name_of_execute_unit_test>.py
    │       │   └── writeback/
    │       │       └── <name_of_writeback_unit_test>.py
    │       ├── memory/
    │       │   └── <name_of_memory_unit_test>.py
    │       └── <name_of_top_level_test>.py
    └── test_results/
        └── <MM/DD/YYYY>/
            └── results.txt
```


## Branching Strategy

> **Note:** I am looking for a resource that I can attach here that explains the basics of Git. If you have one, please message Seth McConkey (@s3f2607) on Discord. I think a video would be best, but a book/website could work too.

> **Note:** Git is hard. If you don't have a lot of experience with Git, this document probably won't make much sense. If you are blocked because you are confused on what action you should take with regards to Git, feel free to reach out to Seth McConkey (@s3f2607) on Discord.

There are five branches/types of branches that this repository supports:

### 1. `main`

- This branch should always be stable.
- No commits should be made directly into `main`. 
- Changes should be made in `feature/`, `integration/`, or `hotfix/` branches instead. 
- When all changes are finalized, the `feature/`, `integration/`, or `hotfix/` branch should be merged into `main`


### 2. `feature/<feature-name>`

- `feature/` branches are temporary branches used to contain work-in-progress changes specific to one task.
- They are used so that `main` is kept stable. 
- They keep the repository organized so that features can be easily tracked and found.
- The name of a `feature/` branch should be short and descriptive, and always contain `feature/` as a prefix.
  - **Example:** A change implementing a new Square Root functional unit should have a feature branch with a name like `feature/sqrt-unit`
- `feature/` branches should only contain changes relevant to the target feature. Unrelated changes should be put into a different `feature/` branch.
  - **Example:** If I want to make a modification to the Trignometric functional unit, those changes should not be included in the `feature/sqrt-unit` branch. A new `feature/` branch should be created for those changes.
  
- Once a feature is finished and it has been tested, it can be merged into `main` or an `integration/` branch.
  - After it is merged, the `feature/` branch should be deleted immediately.
  - > Note: Once a branch is deleted, that branch's name can be reused for another feature in the future, if necessary.

### 3. `integration/<integration-name>`

- `integration/` branches are used to combine multiple `feature/` branches and integrate them before merging the `feature/` branches into `main`. 
- `integration/` branches allow for features that are dependent on each other to be combined and tested without breaking `main`
  - **Example:** If there is a feature that modifies the Issue stage and a feature that modifies the Fetch stage, they should be merged into an `integration/` branch (`integration/fetch-issue`).
- The names of `integration/` branches should briefly describe the two features being integrated and contain the prefix `integration/`
- Once all changes are made that sucessfully integrate two or more features, and all of the tests pass, the `integration/` branch may be merged into `main`.
  - After it is merged, the `integration/` branch should be deleted immediately.

### 4. `hotfix/`

- If changes are made in `feature/` or `integration/` branches, and they are sucessfully tested, this type of branch should not be necessary
  - However, mistakes happen, so a `hotfix/` branch should be used when `main` is broken
- If `main` is discovered to be broken, a `hotfix/` branch should be created that contain all changes necessary to fix the issue.
- After the change is tested, it can be merged into `main`
  - After it is merged, the `hotfix/` branch should be deleted immediately.

### 5. `archive`

- If a `feature/` or `integration/` is abandoned (and not merged back into `main`), it is to be merged into the `archive` branch before it is deleted to preserve the git history 

### Example Workflows

#### New Feature

- Clone or fetch updates from the `cardinal` repository: 

  ```
  git clone https://github.com/Purdue-SoCET/cardinal/tree/main`
  ```

  OR 

  ```
  cd <directory>/cardinal
  git fetch origin
  ```

- Checkout the `main` branch

  ```
  git checkout origin/main
  ```

- Pull all latest changes from the repository

  ```
  git pull
  ```

- Create a new feature branch

  ```
  git checkout -b feature/<feature-name>
  ```

- Add, commit, and push changes to the `feature/` branch

  ```
  git add <filename>
  git commit -m "your commit message here"
  git push origin
  ```

- Run tests and make sure they all pass
- Merge `main` into your feature branch

  ```
  git fetch origin
  git merge origin/main
  ```

- Fix conflicts and run tests again
- Merge your `feature/` branch into `main` and delete the `feature/` branch

  ```
  git checkout origin/main
  git merge feature/<feature-name>
  git push origin
  git push origin --delete feature/<feature-name>
  ```

