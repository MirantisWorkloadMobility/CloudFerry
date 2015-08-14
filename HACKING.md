# CloudFerry Contributing Documentation

## How to Contribute

CloudFerry development process follows standard [pull-request model](
https://help.github.com/articles/using-pull-requests/).

 1. [Fork](https://help.github.com/articles/fork-a-repo/) CloudFerry repository
    to your personal Github account
 2. Checkout `devel` branch (this is the primary development branch)
    ```
    cd CloudFerry
    git checkout devel
    ```
 3. Create branch in your local repository
    ```
    cd CloudFerry
    git checkout -b my-new-feature
    ```
 4. Implement changes in your local branch with following rules in mind:
    - Unittests must be written for new functionality
    - Functional tests must succeed
    - pep8 checks succeed
 5. Push code to your forked repo
    ```
    git push forked_repo my-new-feature
    ```
 6. [Create pull request](https://help.github.com/articles/using-pull-requests/#initiating-the-pull-request)
    from Github UI
 7. Wait for
    - Two positive reviews from other team members
    - Unit tests job succeed
    - Functional tests job succeed

## General Rules

 * Unit tests
    * MUST pass
    * New functionality must be covered with unit tests
 * Functional tests
    * MUST pass
    * New major functionality MUST have functional tests available
 * Static analysis
    * New functionality
       - pylint checks with warnings level and above must be fixed
       - pep8 should be followed
    * Old code
       - pylint checks with warnings and above must be fixed for newly
         introduced functionality
       - pep8 checks – existing code should not be modified

## Code Review

 * Two +1s required for merge
 * Functional review has highest priority
 * Style checks have lower priority

## Branching Strategy

 * There are 2 branches:
      * Development branch (devel)
      * Release branch (master)
 * Each feature/bugfix is developed in a forked repo and submitted
   through [pull request](https://help.github.com/articles/using-pull-requests/)
 * All committers push their changes to devel fist
 * The code is reviewed by all participants
 * Two +1s required for the feature to be merged into devel
 * Once the code is end-to-end verified by QA it gets merged into master
 * master is considered to have the latest working code
 * Release versions are based on [semantic versioning](http://semver.org/)

