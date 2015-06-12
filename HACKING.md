# CloudFerry Contributing Documentation

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

# Static Analysis Tools Versions

Tool   | Version | Configuration
-------|---------|--------------
pylint | 1.4.3   | default
pep8   | 1.5.7   | default
flake8 | 2.4.0   | default

All the static tools with correct versions are installed inside cloudferry VM
of [development environment](devlab/README.md).

