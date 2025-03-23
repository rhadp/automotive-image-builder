#!/usr/bin/bash

if [ ! -d ${OUTDIR} ]; then
    mkdir -p ${OUTDIR}
    mkdir -p ${BUILDIR}
    mkdir -p ${RUNDIR}
fi

