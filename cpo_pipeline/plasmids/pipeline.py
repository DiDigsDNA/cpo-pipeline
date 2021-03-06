#!/usr/bin/env python

import argparse
import configparser
import csv
import datetime
import errno
import glob
import itertools
import logging
import multiprocessing
import os
import operator
import re
import shutil
import structlog
import sys
import urllib.request
from pprint import pprint
import drmaa

from pkg_resources import resource_filename

from cpo_pipeline.drmaa import prepare_job, run_jobs
from cpo_pipeline.logging import now
from cpo_pipeline.assembly.parsers import result_parsers
from cpo_pipeline.plasmids import parsers
from cpo_pipeline.plasmids import strategies


logger = structlog.get_logger()

def main(args):
    """
    main entrypoint
    Args:
        args():
    Returns:
        (void)
    """

    config = configparser.ConfigParser()
    config.read(args.config_file)

    try:
        mash_refseq_plasmid_db = args.mash_refseq_plasmid_db
    except AttributeError:
        try:
            mash_refseq_plasmid_db = config['databases']['mash_refseq_plasmid_db']
            if not os.path.exists(mash_refseq_plasmid_db):
                raise FileNotFoundError(
                    errno.ENOENT, os.strerror(errno.ENOENT), mash_refseq_plasmid_db
                )
            logger.info(
                "configuration_loaded",
                timestamp=str(now()),
                configuration_attribute="databases/mash_refseq_plasmid_db",
                configuration_value=mash_refseq_plasmid_db,
            )
        except Exception as e:
            logger.error(
                "configuration_failed",
                timestamp=str(now()),
                configuration_attribute="databases/mash_refseq_plasmid_db",
                error_message=str(e),
            )

    try:
        mash_custom_plasmid_db = args.mash_custom_plasmid_db
    except AttributeError:
        try:
            mash_custom_plasmid_db = config['databases']['mash_custom_plasmid_db']
            if not os.path.exists(mash_custom_plasmid_db):
                raise FileNotFoundError(
                    errno.ENOENT, os.strerror(errno.ENOENT), mash_custom_plasmid_db
                )
            logger.info(
                "configuration_loaded",
                timestamp=str(now()),
                configuration_attribute="databases/mash_custom_plasmid_db",
                configuration_value=mash_custom_plasmid_db,
            )
        except Exception as e:
            logger.error(
                "configuration_failed",
                timestamp=str(now()),
                configuration_attribute="databases/mash_custom_plasmid_db",
                error_message=str(e),
            )


    sample_id = args.sample_id
    output_dir = args.outdir
        

    paths = {
        'job_scripts': resource_filename('data', 'job_scripts'),
        'reads1_fastq': args.reads1_fastq,
        'reads2_fastq': args.reads2_fastq,
        'mash_custom_plasmid_db': mash_custom_plasmid_db,
        'mash_refseq_plasmid_db': mash_refseq_plasmid_db,
        'output_dir': output_dir,
        'logs': os.path.join(
            output_dir,
            sample_id,
            'logs',
        ),
        'plasmid_output': os.path.join(
            output_dir,
            sample_id,
            "plasmids",
        ),
        "refseq_plasmid_output": os.path.join(
            output_dir,
            sample_id,
            "plasmids",
            "refseq_plasmids",
        ),
        "custom_plasmid_output": os.path.join(
            output_dir,
            sample_id,
            "plasmids",
            "custom_plasmids",
        ),
    }

    os.makedirs(
        paths['logs'],
        exist_ok=True
    )

    os.makedirs(
        os.path.join(
            paths['custom_plasmid_output'],
            'candidates',
        ),
        exist_ok=True
    )

    os.makedirs(
        os.path.join(
            paths['refseq_plasmid_output'],
            'candidates',
        ),
        exist_ok=True
    )

    refseq_candidates = strategies.refseq_plasmids(sample_id, paths)
    custom_candidates = strategies.custom_plasmids(sample_id, paths)

    candidates = refseq_candidates + custom_candidates
    
    samtools_faidx_jobs = []
    bwa_index_jobs = []
    for candidate in candidates:
        samtools_faidx_job = {
            'job_name': "_".join(['samtools_faidx', sample_id, candidate['accession']]),
            'output_path': paths['logs'],
            'error_path': paths['logs'],
            'native_specification': '-pe smp 2',
            'remote_command': os.path.join(paths['job_scripts'], 'samtools_faidx.sh'),
            'args': [
                "--fasta", candidate['fasta_path'],
            ]
        }
        bwa_index_job = {
            'job_name': "_".join(['bwa_index', sample_id, candidate['accession']]),
            'output_path': paths['logs'],
            'error_path': paths['logs'],
            'native_specification': '-pe smp 2',
            'remote_command': os.path.join(paths['job_scripts'], 'bwa_index.sh'),
            'args': [
                "--fasta", candidate['fasta_path'],
            ]
        }
        samtools_faidx_jobs.append(samtools_faidx_job)
        bwa_index_jobs.append(bwa_index_job)

    run_jobs(samtools_faidx_jobs + bwa_index_jobs)

    bwa_mem_jobs = []
    for candidate in candidates:
        bwa_mem_job = {
            'job_name': "_".join(['bwa_mem', sample_id, candidate['accession']]),
            'output_path': paths['logs'],
            'error_path': paths['logs'],
            'native_specification': '-pe smp 8 -shell y',
            'remote_command': os.path.join(paths['job_scripts'], 'bwa_mem.sh'),
            'args': [
                "--reference", candidate['fasta_path'],
                "--R1", paths['reads1_fastq'],
                "--R2", paths['reads2_fastq'],
                "--output", re.sub("\.fna$", ".sam", candidate['fasta_path'])
            ]
        }
        bwa_mem_jobs.append(bwa_mem_job)

    run_jobs(bwa_mem_jobs)


    samtools_filter_fixmate_sort_jobs = []
    for candidate in candidates:
        alignment = os.path.join(
            re.sub("\.fna$", ".sam", candidate['fasta_path'])
        )
        samtools_filter_fixmate_sort_job = {
            'job_name': "_".join(['samtools_filter_fixmate_sort', sample_id, candidate['accession']]),
            'output_path': paths['logs'],
            'error_path': paths['logs'],
            'native_specification': '-pe smp 4',
            'remote_command': os.path.join(paths['job_scripts'], 'samtools_filter_fixmate_sort.sh'),
            'args': [
                "--input", alignment,
                "--flags", 1540,
                "--output", re.sub('\.sam$', '.bam', alignment),
            ]
        }
        samtools_filter_fixmate_sort_jobs.append(samtools_filter_fixmate_sort_job)

    run_jobs(samtools_filter_fixmate_sort_jobs)

    for candidate in candidates:
        sam_alignment = "/".join([
            re.sub('\.fna$', '.sam', candidate['fasta_path']),
        ])
        os.remove(sam_alignment)

    samtools_index_jobs = []
    for candidate in candidates:
        alignment = os.path.join(
            re.sub('\.fna', '.bam', candidate['fasta_path'])
        )
        samtools_index_job = {
            'job_name': "_".join(['samtools_index', sample_id, candidate['accession']]),
            'output_path': paths['logs'],
            'error_path': paths['logs'],
            'native_specification': '-pe smp 4',
            'remote_command': os.path.join(paths['job_scripts'], 'samtools_index.sh'),
            'args': [
                "--input", alignment,
            ]
        }
        samtools_index_jobs.append(samtools_index_job)

    run_jobs(samtools_index_jobs)

    samtools_depth_jobs = []
    for candidate in candidates:
        alignment = os.path.join(
            re.sub('\.fna', '.bam', candidate['fasta_path'])
        )
        samtools_depth_job = {
            'job_name': "_".join(['samtools_depth', sample_id, candidate['accession']]),
            'output_path': paths['logs'],
            'error_path': paths['logs'],
            'native_specification': '-pe smp 1',
            'remote_command': os.path.join(paths['job_scripts'], 'samtools_depth.sh'),
            'args': [
                "--input", alignment,
                "--output", re.sub('\.bam$', '.depth', alignment),
            ]
        }
        samtools_depth_jobs.append(samtools_depth_job)

    run_jobs(samtools_depth_jobs)

    for candidate in candidates:
        depth = os.path.join(
            re.sub('\.fna$', '.depth', candidate['fasta_path']),
        )
        MINIMUM_DEPTH = 10
        MINIMUM_COVERAGE_PERCENT = 95.0
        positions_above_minimum_depth = 0
        total_length = 0
        with open(depth) as depth_file:
            for line in depth_file:
                [_, position, depth] = line.split()
                total_length += 1
                if int(depth) >= MINIMUM_DEPTH:
                    positions_above_minimum_depth += 1
        candidate['bases_above_minimum_depth'] = positions_above_minimum_depth
        try:
            candidate['percent_above_minimum_depth'] = positions_above_minimum_depth / total_length
        except ZeroDivisionError:
            candidate['percent_above_minimum_depth'] = 0.0

    freebayes_jobs = []
    for candidate in candidates:
        alignment = re.sub(
            '\.fna$', '.bam', candidate['fasta_path']
        )
        reference = candidate['fasta_path']
        vcf = re.sub(
            '\.fna$', '.vcf', candidate['fasta_path']
        )
        freebayes_job = {
            'job_name': "_".join(['freebayes', sample_id, candidate['accession']]),
            'output_path': paths['logs'],
            'error_path': paths['logs'],            'native_specification': '-pe smp 8',
            'remote_command': os.path.join(paths['job_scripts'], 'freebayes.sh'),
            'args': [
                "--input", alignment,
                "--reference", reference,
                "--output", vcf,
            ]
        }
        freebayes_jobs.append(freebayes_job)

    run_jobs(freebayes_jobs)


    bcftools_view_jobs = []
    for candidate in candidates:
        vcf = re.sub(
            '\.fna$', '.vcf', candidate['fasta_path']
        )
        bcftools_view_job = {
            'job_name': "_".join(['bcftools_view', sample_id, candidate['accession']]),
            'output_path': paths['logs'],
            'error_path': paths['logs'],
            'native_specification': '-pe smp 2 -shell y',
            'remote_command': os.path.join(paths['job_scripts'], 'bcftools_view.sh'),
            'args': [
                "--input", vcf,
                "--output", re.sub('\.vcf$', '.snps.vcf', vcf),
            ]
        }
        bcftools_view_jobs.append(bcftools_view_job)

    run_jobs(bcftools_view_jobs)

    for candidate in candidates:
        snps_vcf = re.sub(
            '\.fna$', '.snps.vcf', candidate['fasta_path']
        )
        snps = 0
        with open(snps_vcf, 'r') as f:
            for line in f:
                if not line.startswith('#'):
                    snps += 1
        candidate['snps'] = snps

    plasmid_output_summary = os.path.join(
        paths['plasmid_output'],
        'custom_plasmid.txt'
    )

    
    plasmid_output_final = os.path.join(
        output_dir,
        sample_id,
        'final_plasmid.tsv'
    )
    
    custom_candidates = [c for c in candidates if c['database'] == 'custom']
    custom_candidates.sort(key=operator.itemgetter('snps'))
    custom_candidates.sort(key=operator.itemgetter('plasmid_length'), reverse=True)
    custom_candidates.sort(key=operator.itemgetter('percent_above_minimum_depth'), reverse=True)
    custom_best_candidate = next(iter(custom_candidates), None)

    with open(plasmid_output_final, 'w+') as f:
        fieldnames = [
            'sample_id',
            'accession',
            'circularity',
            'plasmid_length',
            'bases_above_minimum_depth',
            'percent_above_minimum_depth',
            'snps',
            'allele',
            'incompatibility_group'
        ]

        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter='\t', extrasaction='ignore')
        writer.writeheader()
        if custom_best_candidate:
            f.write(args.sample_id + '\t')
            # Truncate floats to 4 digits
            writer.writerow({k:round(v,4) if isinstance(v,float) else v for k,v in custom_best_candidate.items()})

    with open(plasmid_output_summary, 'w+') as f:
        fieldnames = [
        'sample_id',
            'accession',
            'circularity',
            'plasmid_length',
            'bases_above_minimum_depth',
            'percent_above_minimum_depth',
            'snps',
            'allele',
            'incompatibility_group'
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter='\t', extrasaction='ignore')
        writer.writeheader()
        for candidate in custom_candidates:
            f.write(args.sample_id + '\t')
            # Truncate floats to 4 digits
            writer.writerow({k:round(v,4) if isinstance(v,float) else v for k,v in candidate.items()})
    
    
if __name__ == "__main__":
    script_name = os.path.basename(os.path.realpath(sys.argv[0]))
    parser = argparse.ArgumentParser(prog=script_name, description='')
    parser.add_argument("-i", "--ID", dest="sample_id",
                        help="identifier of the isolate", required=True)
    parser.add_argument("-1", "--R1", dest="reads1_fastq",
                        help="absolute file path forward read (R1)", required=True)
    parser.add_argument("-2", "--R2", dest="reads2_fastq",
                        help="absolute file path to reverse read (R2)", required=True)
    parser.add_argument("-o", "--outdir", dest="output", default='./',
                        help="absolute path to output folder")
    parser.add_argument("--mash-refseq-plasmiddb", dest="mash_refseq_plasmid_db",
                        help="absolute path to mash reference database")
    parser.add_argument("--mash-custom-plasmiddb", dest="mash_custom_plasmid_db",
                        help="absolute file path to directory of custom plasmid mash sketches")
    parser.add_argument('-c', '--config', dest='config_file',
                        default=resource_filename('data', 'config.ini'),
                        help='Config File', required=False)

    args = parser.parse_args()

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.DEBUG,
    )

    structlog.configure_once(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.processors.JSONRenderer()
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=structlog.threadlocal.wrap_dict(dict),
    )

    logger = structlog.get_logger(
        analysis_id=str(uuid.uuid4()),
        sample_id=args.sample_id,
        pipeline_version=cpo_pipeline.__version__,
    )

    logger.info(
        "analysis_started",
        timestamp=str(now()),
    )

    main(args)
