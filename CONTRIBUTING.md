# SoCET GPU Contributing Guide - WORK IN PROGRESS

> **Note:** This is a work in progress. Any feedback is greatly appreciated. Message Seth McConkey (@s3f2607) on Discord

> **Note:** If viewing this file in VS Code, use `CTRL + SHIFT + V` to render this Markdown file in a neat format

- [SoCET GPU Contributing Guide - WORK IN PROGRESS](#socet-gpu-contributing-guide---work-in-progress)
  - [Directory Structure (Work In Progress)](#directory-structure-work-in-progress)
  - [Branching Strategy](#branching-strategy)
    - [1. `main`](#1-main)
    - [2. `feature/<feature-name>`](#2-featurefeature-name)
    - [3. `integration/<integration-name>`](#3-integrationintegration-name)
    - [4. `hotfix/`](#4-hotfix)
    - [5. `archive`](#5-archive)
    - [Example Workflows](#example-workflows)
      - [Creating a New Feature](#creating-a-new-feature)
      - [Integrating Features](#integrating-features)
    - [Example Scenarios](#example-scenarios)
      - [Collaborating on an `integration/` or `feature/` Branch](#collaborating-on-an-integration-or-feature-branch)


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

#### Creating a New Feature

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

- Make necessary changes to your feature

- Add, commit, and push changes to the `feature/` branch. Do this as often as you want

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

- Fix conflicts and run tests again, make sure they pass
- When all tests pass again, merge your `feature/` branch into `main` and delete the `feature/` branch

  ```
  git checkout origin/main
  git merge feature/<feature-name>
  git push origin
  git push origin --delete feature/<feature-name>
  ```

#### Integrating Features

- Clone or fetch updates from the `cardinal` repository: 

  ```
  git clone https://github.com/Purdue-SoCET/cardinal/tree/main`
  ```

  OR 

  ```
  cd <directory>/cardinal
  git fetch origin
  ```

- Checkout one of the `feature/` branches you are looking to integrate
  
  ```
  git checkout origin/feature/a
  ```

- Create an `integration/` branch from the `feature/a` branch
 
  ```
  git checkout -b integration/a-b
  ```

- Merge the `feature/b` branch into the `integration/a-b` branch

  ```
  git fetch origin
  git merge origin/feature/b
  ```

- Fix all conflicts
- Make all changes necessary to integrate the two features
- Add, commit, and push changes to the `integration/a-b` branch. Do this as often as you want

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

- Fix conflicts and run tests again, make sure they pass
- When all tests pass again, merge the `integration/a-b` branch into `main` and delete the `integration/a-b` branch

  ```
  git checkout origin/main
  git merge integration/a-b
  git push origin
  git push origin --delete integration/a-b
  ```

### Example Scenarios

#### Collaborating on an `integration/` or `feature/` Branch

Some common scenarios when working with someone else on the same branch:
  
- **Your teammate has pushed their commits, and you have some commits you haven't pushed yet. You try to pull their changes, but you get a warning that you might lose the changes in your commits**

  - Rebase your commits on top of theirs
    ```
    git pull origin --rebase
    ```
  - Fix any conflicts that come up
  - Push your changes
    ```
    git push origin
    ```

- **Your teammate has pushed their commits, and you have some changes you haven't committed yet. You try to pull their changes, but you get a warning that you might lose the changes you haven't committed yet**

  - Stash your changes
    ```
    git stash push path/to/your/file
    ```

    OR stash all of your unstaged changes

    ```
    git stash
    ```

  - Pull the changes from the GitHub repository
    ```
    git pull origin
    ```

  - List all the stashes you have made
    ```
    git stash list 
    ```
    - This will list them out, with the most recent stash made being at index 0, and so on
  
  - Apply the desired stash
    ```
    git stash apply 0
    ```
    - This applies the changes from the most recent stash you made. You can substitute a different number for 0 if you want the changes from a different stash. You may have to apply multiple stashes if you used `git stash push` for multiple files.
  
  - Fix any conflicts
  - Now you should have the latest changes from the GitHub repository and your changes
  


