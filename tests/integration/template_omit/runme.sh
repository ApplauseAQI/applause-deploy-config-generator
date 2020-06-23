#!/bin/bash

TEST_DIR=$(dirname $0)
cd ${TEST_DIR}

export PYTHONPATH=../../..

rm -rf tmp
mkdir tmp

(
set -x

python -m deploy_config_generator -c site_config.yml -o tmp . $@
)

diff -ru expected_output tmp
