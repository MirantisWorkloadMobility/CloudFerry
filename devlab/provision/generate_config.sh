#!/bin/bash

cloudferry_dir=$(cd "$( dirname "${BASH_SOURCE[0]}" )/../.." && pwd)
result_config=${cloudferry_dir}/configuration.ini

echo "Preparing configuration for CloudFerry"
cp ${cloudferry_dir}/devlab/config.template ${result_config}

while read key value
do
    value=($value)
    value=${value[1]}
    if [[ -n ${value} ]]; then
      sed -i "s|<${key}>|${value}|g" ${result_config}
    fi
done < ${cloudferry_dir}/devlab/config.ini

echo "CloudFerry config is saved in ${result_config}"
