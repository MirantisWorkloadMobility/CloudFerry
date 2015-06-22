#!/bin/bash

SCRIPT=$(basename $0)

error_exit() {
    local message=$1

    if [[ -n $message ]]; then
        echo $message &>2
        echo &>2
    fi

    echo "Usage: ${SCRIPT} --cloudferry-path <path>"

    exit 1
}


while [[ $# -ge 1 ]]; do
    case $1 in
        --cloudferry-path) shift; CF_PATH=$1; shift;;
        *) error_exit "Invalid arg $1";;
    esac
done

[[ -z $CF_PATH ]] && error_exit "Missing --cloudferry-path option"

result_config=${CF_PATH}/configuration.ini

echo "Preparing configuration for CloudFerry"
cp ${CF_PATH}/devlab/config.template ${result_config}

while read key value
do
    value=($value)
    value=${value[1]}
    if [[ -n ${value} ]]; then
      sed -i "s|<${key}>|${value}|g" ${result_config}
    fi
done < ${CF_PATH}/devlab/config.ini

echo "CloudFerry config is saved in ${result_config}"
