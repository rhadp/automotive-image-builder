#!/usr/bin/bash


turn_tracing_off() {
    local _tracing_enabled=0
    if [[ "$-" =~ x ]]; then
        _tracing_enabled=1
    fi
    set +x
    echo $_tracing_enabled
}

restore_tracing_state() {
    local _tracing_enabled=${1:-1}
    if [ $_tracing_enabled -eq 1 ]; then
        set -x
    fi
}

_acquire_session() {
    local pool_name=$1
    local session_file=$2

    local tracing_status=$(turn_tracing_off)
    duffy client \
        request-session \
        pool=${pool_name},quantity=1 > $session_file
    restore_tracing_state $tracing_status
}

get_aws_session() {
    local pool_name=$1
    local session_file=$2
    local delay=${3:-5}
    local retry=${4:-10}
    local count=0
    local result=1

    while [ "$result" -ne 0 ] && [ "$count" -lt "$retry" ]; do
        _acquire_session $pool_name $session_file
        err_msg=$(get_error_detail_from_session $session_file)
        if [ -f "$session_file" ] && [ -n "$err_msg" ]; then
            return 0
        else
            echo "Error getting an AWS host session: $err_msg"
            echo "Retrying after $delay minutes ..."
            sleep ${delay}m
            count=$(( $count + 1 ))
        fi
    done

    echo "Unable to get an AWS host session after ${retry} retries"
    return 1
}

_get_value_from_session() {
    local session_file=$1
    local key=$2

    jq $key $session_file | sed -e 's|"||g'
}

get_error_detail_from_session() {
    local session_file=$1

    _get_value_from_session $session_file '.error.detail'
}

get_ip_from_session() {
    local session_file=$1

    _get_value_from_session $session_file '.session.nodes[].data.provision.public_ipaddress'
}

get_session_id_from_session() {
    local session_file=$1

    _get_value_from_session $session_file '.session.id'
}

release_aws_session() {
    local session_file=$1
    local session_id=$(get_session_id_from_session $session_file)

    echo "Closing AWS session ..."
    local tracing_status=$(turn_tracing_off)
    duffy client \
        retire-session $session_id > /dev/null
    [ -f $session_file ] && rm -f $session_file
    restore_tracing_state $tracing_status
}
