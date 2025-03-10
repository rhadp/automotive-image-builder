#!/usr/bin/bash

if [ ! -d ${OUTDIR} ]; then
    mkdir -p ${OUTDIR}
    mkdir -p ${BUILDDIR}
    mkdir -p ${RUNDIR}
fi

