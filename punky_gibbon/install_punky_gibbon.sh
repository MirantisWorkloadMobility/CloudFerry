#!/usr/bin/env bash

LOCAL_IP=${1}
RANDOM_CHANCE=${2}
API_PASTE_CONFIGS="/etc/nova/api-paste.ini /etc/glance/glance-api-paste.ini /etc/cinder/api-paste.ini"
SERVICES="nova-api glance-api cinder-api"

install_punky_gibbon() {
    local FILE=${1}
    local SECTION=${2}
    local OPTION=${3}


    if VALUE=$(crudini --get "${FILE}" "${SECTION}" ${OPTION} | grep -v punky_gibbon); then
        echo "Installing Punky Gibbon to ${FILE} [${SECTION}]${OPTION} = ${VALUE}"
        crudini --set --existing "${FILE}" "${SECTION}" "${OPTION}" "punky_gibbon ${VALUE}"
    fi
}

for config_file in ${API_PASTE_CONFIGS}; do
    for section in $(crudini --get "${config_file}"); do
        if [[ ${section} == pipeline:* ]]; then
            install_punky_gibbon "${config_file}" "${section}" pipeline
        elif [[ ${section} == composite:* && $(crudini --get "${config_file}" "${section}" use) == *:pipeline_factory ]]; then
            for option in $(crudini --get "${config_file}" "${section}" | grep -v use); do
                install_punky_gibbon "${config_file}" "${section}" "${option}"
            done
        fi
    done

    crudini --set "${config_file}" "filter:punky_gibbon" "paste.filter_app_factory" "punky_gibbon.middleware:PunkyGibbon"
    crudini --set "${config_file}" "filter:punky_gibbon" "ignore_ips" "127.0.0.1,${LOCAL_IP}"
    crudini --set "${config_file}" "filter:punky_gibbon" "random_chance" "${RANDOM_CHANCE}"
done

for service in ${SERVICES}; do
    service ${service} restart
done
