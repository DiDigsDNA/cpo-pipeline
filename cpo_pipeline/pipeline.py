#!/usr/bin/env python

import os
import argparse
import configparser
import csv
import subprocess

import cpo_pipeline

def prepare_job(job, session):
    job_template = session.createJobTemplate()
    job_template.jobName = job['job_name']
    job_template.nativeSpecification = job['native_specification']
    job_template.jobEnvironment = os.environ
    job_template.workingDirectory = os.getcwd()
    job_template.remoteCommand = job['remote_command']
    job_template.args = job['args']
    job_template.joinFiles = True
    
    return job_template

def main(args, config):
    with open(args.input_file) as input_file:
        fieldnames = ['sample_id', 'reads1_fastq', 'reads2_fastq']
        reader = csv.DictReader(
            (row for row in input_file if not row.startswith('#')),
            delimiter='\t',
            fieldnames=fieldnames
        )
        for row in reader:
            command_line = [
                'cpo-pipeline',
                'assembly',
                '--ID', row['sample_id'],
                '--R1', row['reads1_fastq'],
                '--R2', row['reads1_fastq'],
                '--outdir', args.outdir,
            ]
            subprocess.run(command_line)

if __name__ == '__main__':
    config = configparser.ConfigParser()
    config_file = resource_filename('data', 'config.ini')
    config.read(config_file)
    script_name = os.path.basename(os.path.realpath(sys.argv[0]))
    parser = argparse.ArgumentParser(prog=script_name, description='')
    parser.add_argument('-i', '--ID',  dest='sample_id',
                        help='Sample ID', required=False)
    parser.add_argument('-1', '--R1', dest='reads1_fastq',
                        help='Read 1 fastq(.gz) file', required=False)
    parser.add_argument('-2', '--R2', dest='reads2_fastq',
                        help='Read 2 fastq(.gz) file', required=False)
    parser.add_argument('-o', '--output', dest='output',
                        help='Output Directory', required=False)
    parser.add_argument('-v', '--version', action='version',
                        version='%(prog)s {}'.format(cpo_pipeline.__version__))
    args = parser.parse_args()
    main()
