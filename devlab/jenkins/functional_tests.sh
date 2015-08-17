#!/bin/bash
set -e
set -x

export WORKSPACE="${WORKSPACE:-$( cd $( dirname "$0" ) && cd ../../../ && pwd)}"
export CF_DIR=$WORKSPACE/cloudferry
export JOB_NAME="${JOB_NAME:-cloudferry-functional-tests}"
export BUILD_NUMBER="${BUILD_NUMBER:-$[ 1 + $[ RANDOM % 1000 ]]}"
export BUILD_NAME="-$(echo $JOB_NAME | sed s/cloudferry/cf/)-${BUILD_NUMBER}"
export VIRTUALBOX_NETWORK_NAME="vn-${JOB_NAME}-${BUILD_NUMBER}"

trap 'clean_exit $LINENO $BASH_COMMAND; exit' SIGHUP SIGINT SIGQUIT SIGTERM EXIT
clean_exit()
{
    pushd ${CF_DIR}/devlab
    vboxmanage list vms
    vagrant status
    vagrant destroy --force
    vboxmanage list vms
    vagrant status
    popd
}

echo "Preparing environment"

pushd $CF_DIR

if [ "$JOB_NAME" = "cloudferry-functional-tests" ]; then
    git remote update
    # cloudferry source dir is not deleted after job finish, so if
    # pull request cannot be automatically rebased, we must abort it explicitly and
    # exit with failure. In case rebase succeeded, functional test should # move on.
    git pull --rebase origin devel || ( git rebase --abort && exit 1 )
elif  [ "$JOB_NAME" = "cloudferry-release-builder" ]; then
    echo "Job ${JOB_NAME} is running, 'git remote update' and 'git pull --rebase origin devel' was performed previously"
else
    echo "JOB_NAME defined incorrectly"
    exit 1
fi

echo "Create code archive"
cd ${WORKSPACE}/
rm -f cloudferry.tar.gz
tar cvfz cloudferry.tar.gz cloudferry/

echo "Put all steps below"
${CF_DIR}/devlab/jenkins/setup_lab.sh
${CF_DIR}/devlab/jenkins/copy_code_to_cf.sh
${CF_DIR}/devlab/jenkins/gen_load_and_migration.sh
${CF_DIR}/devlab/jenkins/nosetests.sh
