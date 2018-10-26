#!/usr/bin/env python

'''
This script is a wrapper for module two, part 1: typing and resistance gene idenfification from assemblies. 

It uses mlst, resfinder, plasmidfinder, rgi, mobsuite for sequence typing, AMR profile prediction and plasmid predictions. 
The output is a TSV summary of the results. 

Example usage:

  pipeline.py --id BC11-Kpn005 --assembly BC11-Kpn005_S2.fa --output output --expected-species "Klebsiella"

Requires the pipeline_prediction.sh script. the directory of where it's store can be specified using -k.
'''

import subprocess
import pandas
import optparse
import os
import datetime
import sys
import time
import urllib.request
import gzip
import collections
import json
import numpy
import configparser

from parsers import result_parsers

def read(path):
    return [line.rstrip('\n') for line in open(path)]

def execute(command, curDir):
    process = subprocess.Popen(command, shell=False, cwd=curDir, universal_newlines=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

    # Poll process for new output until finished
    while True:
        nextline = process.stdout.readline()
        if nextline == '' and process.poll() is not None:
            break
        sys.stdout.write(nextline)
        sys.stdout.flush()

    output = process.communicate()[0]
    exitCode = process.returncode

    if (exitCode == 0):
        return output
    else:
        raise subprocess.CalledProcessError(exitCode, command)

def httpGetFile(url, filepath=""):
    if (filepath == ""):
        return urllib.request.urlretrieve(url)
    else:
        urllib.request.urlretrieve(url, filepath)
        return True

def gunzip(inputpath="", outputpath=""):
    if (outputpath == ""):
        with gzip.open(inputpath, 'rb') as f:
            gzContent = f.read()
        return gzContent
    else:
        with gzip.open(inputpath, 'rb') as f:
            gzContent = f.read()
        with open(outputpath, 'wb') as out:
            out.write(gzContent)
        return True

def ToJson(dictObject, outputPath):
    #outDir = outputDir + '/summary/' + ID + ".json/"
    #if not (os.path.exists(outDir)):
        #os.makedirs(outDir)
    #with open(outputPath, 'w') as f:
      #json.dump([ob.__dict__ for ob in dictObject.values()], f, ensure_ascii=False)
    return ""

def main():

    config = configparser.ConfigParser()
    config.read(os.path.dirname(os.path.realpath(sys.argv[0])) + '/config.ini')

    #parses some parameters
    parser = optparse.OptionParser("Usage: %prog [options] arg1 arg2 ...")
    #required
    #MLSTHIT, mobsuite, resfinder, rgi, mlstscheme
    parser.add_option("-i", "--id", dest="id", type="string", help="identifier of the isolate")
    parser.add_option("-a", "--assembly", dest="assembly", type="string", help="Path to assembly file.")
    parser.add_option("-o", "--output", dest="output", default='./', type="string", help="absolute path to output folder")    

    parser.add_option("-s", "--mlst-scheme-map", dest="mlst_scheme_map", default=config['databases']['mlst-scheme-map'], type="string", help="absolute file path to mlst scheme")
    parser.add_option("-k", "--script-path", dest="script_path", default=config['scripts']['script-path'], type="string", help="absolute file path to this script folder")
    parser.add_option("-c", "--card-path", dest="card_path", default=config['databases']['card'], type="string", help="absolute file path to card.json db")
    parser.add_option("-d", "--abricate-datadir", dest="abricate_datadir", default=config['databases']['abricate-datadir'], type="string", help="absolute file path to directory where abricate dbs are stored")
    parser.add_option("-p", "--abricate-cpo-plasmid-db", dest="abricate_cpo_plasmid_db", default=config['databases']['abricate-cpo-plasmid-db'], type="string", help="name of abricate cpo plasmid db to use")
    parser.add_option("-e", "--expected-species", dest="expected_species", default="NA/NA/NA", type="string", help="expected species of the isolate")
    
    # parallelization, useless, these are hard coded to 8cores/64G RAM
    # parser.add_option("-t", "--threads", dest="threads", default=8, type="int", help="number of cpu to use")
    # parser.add_option("-p", "--memory", dest="memory", default=64, type="int", help="memory to use in GB")
    
    (options, args) = parser.parse_args()
    # if len(args) != 8:
        # parser.error("incorrect number of arguments, all 7 is required")
    curDir = os.getcwd()
    ID = str(options.id).lstrip().rstrip()
    assembly = options.assembly
    expected_species = options.expected_species
    script_path = options.script_path
    cardPath = options.card_path
    abricate_datadir = options.abricate_datadir
    abricate_cpo_plasmid_db = options.abricate_cpo_plasmid_db
    mlst_scheme_map = options.mlst_scheme_map
    # plasmidfinder = str(options.plasmidfinder).lstrip().rstrip()
    outputDir = options.output

    notes = []
    #init the output list
    output = []
    jsonOutput = []

    print(str(datetime.datetime.now()) + "\n\nID: " + ID + "\nAssembly: " + assembly)
    output.append(str(datetime.datetime.now()) + "\n\nID: " + ID + "\nAssembly: " + assembly)

    #region call the typing script
    print("running pipeline_typing.sh")
    #input parameters: 1=id, 2=assembly, 3=output, 4=cardPath, 5=abricate_datadir, 6=abricate_cpo_plasmid_db
    cmd = [script_path + "/pipeline_typing.sh", ID, assembly, outputDir, cardPath, abricate_datadir, abricate_cpo_plasmid_db]
    result = execute(cmd, curDir)
    #endregion

    #region parse the mlst results
    
    print("step 3: parsing mlst, plasmid, and amr results")
    
    print("identifying MLST")
    mlst = outputDir + "/typing/" + ID + "/" + ID + ".mlst/" + ID + ".mlst" 
    mlstHit = result_parsers.parse_mlst_result(mlst, mlst_scheme_map)
    ToJson(mlstHit, "mlst.json")
    mlstHit = list(mlstHit.values())[0]

    #endregion

    #region parse mobsuite, resfinder and rgi results
    print("identifying plasmid contigs and amr genes")

    plasmidContigs = []
    likelyPlasmidContigs = []
    origins = []

    #parse mobsuite results
    mobfindercontig = outputDir + "/typing/" + ID + "/" + ID + ".recon/" + "contig_report.txt" 
    mSuite = result_parsers.parse_mobsuite_result(mobfindercontig)
    ToJson(mSuite, "mobsuite.json")
    mobfinderaggregate = outputDir + "/typing/" + ID + "/" + ID + ".recon/" + "mobtyper_aggregate_report.txt" 
    mSuitePlasmids = result_parsers.parse_mobsuite_plasmids(mobfinderaggregate)
    ToJson(mSuitePlasmids, "mobsuitePlasmids.json")

    for key in mSuite:
        if mSuite[key]['contig_num'] not in plasmidContigs and mSuite[key]['contig_num'] not in likelyPlasmidContigs:
            if not (mSuite[key]['rep_type'] == ''):
                plasmidContigs.append(mSuite[key]['contig_num'])
            else:
                likelyPlasmidContigs.append(mSuite[key]['contig_num'])
    for key in mSuite:
        if mSuite[key]['rep_type'] not in origins:
            origins.append(mSuite[key]['rep_type'])

    #parse resfinder AMR results
    abricate = outputDir + "/resistance/" + ID + "/" + ID + ".cp"
    rFinder = result_parsers.parse_resfinder_result(abricate, plasmidContigs, likelyPlasmidContigs)#outputDir + "/predictions/" + ID + ".cp", plasmidContigs, likelyPlasmidContigs) #**********************
    ToJson(rFinder, "resfinder.json")

    rgi = outputDir + "/resistance/" + ID + "/" + ID + ".rgi.txt"
    rgiAMR = result_parsers.parse_rgi_result(rgi, plasmidContigs, likelyPlasmidContigs) # outputDir + "/predictions/" + ID + ".rgi.txt", plasmidContigs, likelyPlasmidContigs)#***********************
    ToJson(rgiAMR, "rgi.json")

    carbapenamases = []
    amrGenes = []
    for keys in rFinder:
        carbapenamases.append(rFinder[keys]['short_gene'] + "(" + rFinder[keys]['source'] + ")")
    for keys in rgiAMR:
        if (rgiAMR[keys]['drug_class'].find("carbapenem") > -1):
            if (rgiAMR[keys]['best_hit_aro'] not in carbapenamases):
                carbapenamases.append(rgiAMR[keys]['best_hit_aro'] + "(" + rgiAMR[keys]['source'] + ")")
        else:
            if (rgiAMR[keys]['best_hit_aro'] not in amrGenes):
                amrGenes.append(rgiAMR[keys]['best_hit_aro'] + "(" + rgiAMR[keys]['source'] + ")")
    #endregion

    #region output parsed mlst information
    print("formatting mlst outputs")
    output.append("\n\n\n~~~~~~~MLST summary~~~~~~~")
    output.append("MLST determined species: " + mlstHit['species'])
    output.append("\nMLST Details: ")
    output.append(mlstHit['row'])

    output.append("\nMLST information: ")
    if (mlstHit['species'] == expected_species):
        output.append("MLST determined species is the same as expected species")
        #notes.append("MLST determined species is the same as expected species")
    else:
        output.append("!!!MLST determined species is NOT the same as expected species, contamination? mislabeling?")
        notes.append("MLST: Not expected species. Possible contamination or mislabeling")

    #endregion

    #region output the parsed plasmid/amr results
    output.append("\n\n\n~~~~~~~~Plasmids~~~~~~~~\n")
    
    output.append("predicted plasmid origins: ")
    output.append(";".join(origins))

    output.append("\ndefinitely plasmid contigs")
    output.append(";".join(plasmidContigs))
    
    output.append("\nlikely plasmid contigs")
    output.append(";".join(likelyPlasmidContigs))

    output.append("\nmob-suite prediction details: ")
    for key in mSuite:
        output.append(mSuite[key]['row'])

    output.append("\n\n\n~~~~~~~~AMR Genes~~~~~~~~\n")
    output.append("predicted carbapenamase Genes: ")
    output.append(",".join(carbapenamases))
    output.append("other RGI AMR Genes: ")
    for key in rgiAMR:
        output.append(rgiAMR[key]['best_hit_aro'] + "(" + rgiAMR[key]['source'] + ")")

    output.append("\nDetails about the carbapenamase Genes: ")
    for key in rFinder:
        output.append(rFinder[key]['row'])
    output.append("\nDetails about the RGI AMR Genes: ")
    for key in rgiAMR:
        output.append(rgiAMR[key]['row'])

    #write summary to a file
    summaryDir = outputDir + "/summary/" + ID
    os.makedirs(summaryDir, exist_ok=True)
    out = open(summaryDir + "/summary.txt", 'w')
    for item in output:
        out.write("%s\n" % item)


    #TSV output
    tsvOut = []
    tsvOut.append("ID\tExpected Species\tMLST Species\tSequence Type\tMLST Scheme\tCarbapenem Resistance Genes\tOther AMR Genes\tTotal Plasmids\tPlasmids ID\tNum_Contigs\tPlasmid Length\tPlasmid RepType\tPlasmid Mobility\tNearest Reference\tDefinitely Plasmid Contigs\tLikely Plasmid Contigs")
    #start with ID
    temp = ""
    temp += (ID + "\t")
    temp += expected_species + "\t"

    #move into MLST
    temp += mlstHit['species'] + "\t"
    temp += str(mlstHit['sequence_type']) + "\t"
    temp += mlstHit['scheme'] + "\t"
    
    #now onto AMR genes
    temp += ";".join(carbapenamases) + "\t"
    temp += ";".join(amrGenes) + "\t"

    #lastly plasmids
    temp+= str(len(mSuitePlasmids)) + "\t"
    plasmidID = ""
    contigs = ""
    lengths = ""
    rep_type = ""
    mobility = ""
    neighbour = ""
    for keys in mSuitePlasmids:
        plasmidID += str(mSuitePlasmids[keys]['mash_neighbor_cluster']) + ";"
        contigs += str(mSuitePlasmids[keys]['num_contigs']) + ";"
        lengths += str(mSuitePlasmids[keys]['total_length']) + ";"
        rep_type += str(mSuitePlasmids[keys]['rep_types']) + ";"
        mobility += str(mSuitePlasmids[keys]['predicted_mobility']) + ";"
        neighbour += str(mSuitePlasmids[keys]['mash_nearest_neighbor']) + ";"
    temp += plasmidID + "\t" + contigs + "\t" + lengths + "\t" + rep_type + "\t" + mobility + "\t" + neighbour + "\t"
    temp += ";".join(plasmidContigs) + "\t"
    temp += ";".join(likelyPlasmidContigs)
    tsvOut.append(temp)

    summaryDir = outputDir + "/summary/" + ID
    out = open(summaryDir + "/summary.tsv", 'w')
    for item in tsvOut:
        out.write("%s\n" % item)
    #endregion

if __name__ == "__main__":
    start = time.time()
    print("Starting workflow...")
    main()
    end = time.time()
    print("Finished!\nThe analysis used: " + str(end - start) + " seconds")
