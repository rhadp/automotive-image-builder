#!/usr/bin/bash

# It can passed as a parameter
MAX_CONCURRENT_TESTS=${1:-5}
PLAN=${2:-connect}

FEELING_SAFE=
if [ "$PLAN" == "local" ]; then
    FEELING_SAFE=--feeling-safe
fi

# TMT_RUN_OPTIONS need to contain all important options for tmt execution
if [ -n "$TMT_RUN_OPTIONS" ]; then
    # It's not possible to pass array type variable through environment, so conversion needed
    read -a TMT_RUN_OPTIONS <<< "$TMT_RUN_OPTIONS"
else
    # By default run tests against locally provisioned VM
    TMT_RUN_OPTIONS=( -eNODE=aib-tests-10 plan --name "$PLAN" )
fi

format_time() {
    local exec_time=$1
    ((h=exec_time/3600))
    ((m=(exec_time%3600)/60))
    ((s=exec_time%60))
    printf "%02d:%02d:%02d" $h $m $s
 }

format_test_id() {
    local test_run_idx=$1
    local test_name=$2
    echo "$(printf "%02d" $(( test_run_idx + 1)))-$test_name"
}

execute_test() {
    local test_run_idx=$1
    local test_name=${TEST_NAMES[$test_run_idx]}
    local start_time

    echo "Starting test '$test_name'"
    start_time=$(date +%s)
    # TODO: simplify when https://github.com/teemtee/tmt/issues/2757 is fixed
    tmt -q $FEELING_SAFE run \
        -i "$(format_test_id "$test_run_idx" "$test_name")" \
        "${TMT_RUN_OPTIONS[@]}" test --name "$test_name" \
        discover prepare provision execute -h tmt --no-progress-bar report &
    local pid=$!
    TEST_START_TIME[$pid]=$start_time
    TEST_PIDS[$pid]=$test_name
}

START_TIME=$(date +%s)

echo "Preparing tests execution"
# Execute phases up to prepare
tmt -q $FEELING_SAFE  run -i "$(format_test_id "-1" "prepare-tests")" -B execute "${TMT_RUN_OPTIONS[@]}"

# Gather discovered tests
mapfile -t TEST_NAMES< <(grep "name:" < ~/.config/tmt/last-run/plans/$PLAN/discover/tests.yaml | sed 's/.*tests\///')
TEST_COUNT=${#TEST_NAMES[@]}


declare -A TEST_PIDS
declare -A TEST_START_TIME
INDEX=0
SUCCESSFUL_TESTS=0

# Start max allowed test executed at the beginning
while [[ $INDEX -lt $TEST_COUNT && ${#TEST_PIDS[@]} -lt $MAX_CONCURRENT_TESTS ]]; do
    execute_test "$INDEX"
    INDEX=$(( INDEX + 1 ))
    sleep 0.1  # Small stagger
done

# Monitor and execute new tests when previous finished
while [[ ${#TEST_PIDS[@]} -gt 0 ]]; do
    # Check for completed builds
    for pid in "${!TEST_PIDS[@]}"; do
        if ! kill -0 "$pid" 2>/dev/null; then
            # Test finished
            wait "$pid"
            exit_code=$?
            exec_time="$(format_time $(($(date +%s) - ${TEST_START_TIME[$pid]})))"
            if [[ $exit_code -ne 0 ]]; then
                echo "Test '${TEST_PIDS[$pid]}' failed in $exec_time"
            else
                echo "Test '${TEST_PIDS[$pid]}' successful in $exec_time"
                SUCCESSFUL_TESTS=$((SUCCESSFUL_TESTS + 1))
            fi
            unset "TEST_START_TIME[$pid]"
            unset "TEST_PIDS[$pid]"

            # Start next test if available
            if [[ $INDEX -lt $TEST_COUNT ]]; then
                execute_test "$INDEX"
                INDEX=$(( INDEX + 1 ))
            fi
        fi
    done

    # Brief pause before next check
    sleep 1
done

# Execute cleanup
echo "Cleaning up tests execution"
tmt -q $FEELING_SAFE run --last -A execute "${TMT_RUN_OPTIONS[@]}"

END_TIME=$(date +%s)

echo "Successfully finished $SUCCESSFUL_TESTS/$TEST_COUNT, overall execution time: $(format_time $((END_TIME - START_TIME)))"
exit $(( TEST_COUNT - SUCCESSFUL_TESTS ))
