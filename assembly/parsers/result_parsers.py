# -*- coding: utf-8 -*-
"""cpo-pipeline.assembly.result_parsers

This module provides functions for parsing result files generated by tools
during the QC & Assembly phase of the cpo-pipeline.
"""

import pandas

def parse_kraken_result(path_to_kraken_result):
    """
    Args:
        path_to_kraken_result (str): Path to the kraken report file.

    Returns:
        dict: Parsed kraken report with species-level results.
        For example:
        { "Escherichia coli": { "fragment_percent": 80.2,
                                "fragment_count_root": 120321,
                                "fragment_count_taxon": 841210,
                                "rank_code": "S",
                                "ncbi_taxon_id": "562",
                                "name": "Escherichia coli",
                                "row": 12
                              }
          "Another species": { "fragment_percent": 12.1,
                               ...
                             }
        }
        See kraken manual for more detail on report fields:
        http://ccb.jhu.edu/software/kraken/MANUAL.html#sample-report-output-format
    """
    kraken_result = {}
    parsed_kraken_report_full = pandas.read_csv(path_to_kraken_result, delimiter='\t', header=None)
    #find all the rows with species level information and discard the rest
    parsed_kraken_report_species_only = parsed_kraken_report_full.loc[
        (parsed_kraken_report_full[3] == "S")
    ]
    for i in range(len(parsed_kraken_report_species_only.index)):
        #find all species above 1%
        if (float((str(parsed_kraken_report_species_only.iloc[i, 0])).strip("%")) > 1.00):
            kraken_species_record = {}
            kraken_species_record['fragment_percent'] = float((str(parsed_kraken_report_species_only.iloc[i, 0])).strip("%"))
            kraken_species_record['fragment_count_root'] = int(parsed_kraken_report_species_only.iloc[i,1])
            kraken_species_record['fragment_count_taxon'] = int(parsed_kraken_report_species_only.iloc[i,2])
            kraken_species_record['rank_code'] = parsed_kraken_report_species_only.iloc[i,3]
            kraken_species_record['ncbi_taxon_id'] = parsed_kraken_report_species_only.iloc[i,4]
            kraken_species_record['name'] = parsed_kraken_report_species_only.iloc[i,5].strip()
            kraken_species_record['row'] = "\t".join(str(x) for x in parsed_kraken_report_species_only.iloc[i].tolist())
            kraken_result[kraken_species_record['name']] = kraken_species_record
    return kraken_result

def parse_fastqc_result(pathToR1qc, pathToR2qc, ID, R1, R2):
    fastqc = pandas.read_csv(pathToR1qc + "summary.txt", delimiter='\t', header=None)
    fastqc = fastqc[0].tolist()

    _fastqcR1 = fastqcResult()
    _fastqcR1.basic = fastqc[0]
    _fastqcR1.perBaseSequenceQuality = fastqc[1]
    _fastqcR1.perTileSequenceQuality = fastqc[2]
    _fastqcR1.perSequenceQualityScores = fastqc[3]
    _fastqcR1.perBaseSequenceContent = fastqc[4]
    _fastqcR1.perSequenceGCContent = fastqc[5]
    _fastqcR1.perBaseNContent = fastqc[6]
    _fastqcR1.sequenceLengthDistribution = fastqc[7]
    _fastqcR1.sequenceDuplicationLevels = fastqc[8]
    _fastqcR1.overrepresentedSequences = fastqc[9]
    _fastqcR1.adapterContent = fastqc[10]
    with open(pathToR1qc + "fastqc_report.html", "r") as input:
        _fastqcR1.fastqcHTMLblob = input.read()

    fastqc = pandas.read_csv(pathToR2qc+ "summary.txt", delimiter='\t', header=None)
    fastqc = fastqc[0].tolist()

    _fastqcR2 = fastqcResult()
    _fastqcR2.basic = fastqc[0]
    _fastqcR2.perBaseSequenceQuality = fastqc[1]
    _fastqcR2.perTileSequenceQuality = fastqc[2]
    _fastqcR2.perSequenceQualityScores = fastqc[3]
    _fastqcR2.perBaseSequenceContent = fastqc[4]
    _fastqcR2.perSequenceGCContent = fastqc[5]
    _fastqcR2.perBaseNContent = fastqc[6]
    _fastqcR2.sequenceLengthDistribution = fastqc[7]
    _fastqcR2.sequenceDuplicationLevels = fastqc[8]
    _fastqcR2.overrepresentedSequences = fastqc[9]
    _fastqcR2.adapterContent = fastqc[10]
    with open(pathToR2qc + "fastqc_report.html", "r") as input:
        _fastqcR2.fastqcHTMLblob = input.read()

    return _fastqcR1, _fastqcR2

def parse_mash_genome_result(pathToMashScreen, size, depth):
    _mashHits = {}
    _PhiX = False
    
    mashScreen = pandas.read_csv(pathToMashScreen, delimiter='\t', header=None) #read mash report
    #0.998697        973/1000        71      0       GCF_000958965.1_matepair4_genomic.fna.gz        [59 seqs] NZ_LAFU01000001.1 Klebsiella pneumoniae strain CDPH5262 contig000001, whole genome shotgun sequence [...]
    #parse mash result, using winner takes all
    scores = mashScreen[1].values 
    scoreCutoff = int(scores[0][:scores[0].index("/")]) - 300 #find the cut off value to use for filtering the report (300 below max)
    index = 0
    #find hits with score within top 300
    for score in scores:
        parsedScore = int(score[:score.index("/")])
        if parsedScore >= scoreCutoff:
            index+=1
        else:
            break

    #parse what the species are.
    for i in range(index):
        mr = MashResult()
        mr.size = size
        mr.depth = depth
        mr.identity = float(mashScreen.ix[i, 0])
        mr.sharedHashes = mashScreen.ix[i, 1]
        mr.medianMultiplicity = int(mashScreen.ix[i, 2])
        mr.pvalue = float(mashScreen.ix[i, 3])
        mr.queryID = mashScreen.ix[i, 4]
        mr.queryComment = mashScreen.ix[i, 5]
        mr.accession = mr.queryComment
        mr.row = "\t".join(str(x) for x in mashScreen.ix[i].tolist())
        qID = mr.queryID
        #find gcf accession
        gcf = (qID[:qID.find("_",5)]).replace("_","")
        gcf = [gcf[i:i+3] for i in range(0, len(gcf), 3)]
        mr.gcf = gcf 
        #find assembly name
        mr.assembly = qID[:qID.find("_genomic.fna.gz")]
        #score = mashScreen.iloc[[i]][1]

        if (mr.queryComment.find("phiX") > -1): #theres phix in top hits, just ignore
            _PhiX=True
            mr.species = "PhiX"
        else: #add the non-phix hits to a list
            start = int(mr.queryComment.index(".")) + 3
            stop = int (mr.queryComment.index(","))
            mr.species = str(mr.queryComment)[start: stop]
            _mashHits[mr.species]=mr
    return _mashHits, _PhiX

def parse_mash_plasmid_result(pathToMashScreen, size, depth):
    mashScreen = pandas.read_csv(pathToMashScreen, delimiter='\t', header=None)

    #parse mash result, using winner takes all
    scores = mashScreen[1].values 
    scoreCutoff = int(scores[0][:scores[0].index("/")]) - 100
    index = 0

    #find hits with score >850
    for score in scores:
        parsedScore = int(score[:score.index("/")])
        if parsedScore >= scoreCutoff:
            index+=1
        else:
            break

    _mashPlasmidHits = {}
    #parse what the species are.
    for i in range(index):
        mr = MashResult()
        mr.size = size
        mr.depth = depth
        mr.identity = float(mashScreen.ix[i, 0])
        mr.sharedHashes = mashScreen.ix[i, 1]
        mr.medianMultiplicity = int(mashScreen.ix[i, 2])
        mr.pvalue = float(mashScreen.ix[i, 3])
        mr.queryID = mashScreen.ix[i, 4] #accession
        mr.queryComment = mashScreen.ix[i, 5] #what is it
        mr.accession = mr.queryID[4:len(mr.queryID)-1]
        mr.row = "\t".join(str(x) for x in mashScreen.ix[i].tolist())
        #score = mashScreen.iloc[[i]][1]
        mr.species = ""
        if (mr.identity >= 0.97):
            _mashPlasmidHits[mr.accession] = mr
    return _mashPlasmidHits

def parse_read_stats(pathToMashLog, pathToTotalBp):
    for s in read(pathToMashLog):
        if (s.find("Estimated genome size:") > -1 ):
            _size = float(s[s.index(": ")+2:])
    _totalbp = float(read(pathToTotalBp)[0])
    _depth = _totalbp / _size
    _depth = float(format(_depth, '.2f'))
    return _size,_depth

def parse_busco_result(pathToBuscoResult):
    buscoOutput = read(pathToBuscoResult)
    if (len(buscoOutput) > 0):
        br = buscoResult()
        br.completeSingle = int(buscoOutput[10].split("\t")[1])
        br.completeDuplicate = int(buscoOutput[11].split("\t")[1])
        br.fragmented = int(buscoOutput[12].split("\t")[1])
        br.mising = int(buscoOutput[13].split("\t")[1])
        br.total = int(buscoOutput[14].split("\t")[1])
        br.buscoResult = buscoOutput
        _buscoResults = br
    else: #it should never be <1.... i think
        raise Exception("x011 this shouldnt happen...i think")
    return _buscoResults

def parse_quast_result(pathToQuastResult):
    qResult = read(pathToQuastResult)
    qr = quastResult()

    qr.contigsCount = int(qResult[int([i for i,x in enumerate(qResult) if x.find("# contigs\t") > -1][-1])].split("\t")[1])
    qr.largestContig = int(qResult[int([i for i,x in enumerate(qResult) if x.find("Largest contig\t") > -1][-1])].split("\t")[1])
    qr.N50 = int(qResult[int([i for i,x in enumerate(qResult) if x.find("N50\t") > -1][-1])].split("\t")[1])
    qr.NG50 = int(qResult[int([i for i,x in enumerate(qResult) if x.find("NG50\t") > -1][-1])].split("\t")[1])
    qr.L50 = int(qResult[int([i for i,x in enumerate(qResult) if x.find("L50\t") > -1][-1])].split("\t")[1])
    qr.LG50 = int(qResult[int([i for i,x in enumerate(qResult) if x.find("LG50\t") > -1][-1])].split("\t")[1])
    qr.N75 = int(qResult[int([i for i,x in enumerate(qResult) if x.find("N75\t") > -1][-1])].split("\t")[1])
    qr.NG75 = int(qResult[int([i for i,x in enumerate(qResult) if x.find("NG75\t") > -1][-1])].split("\t")[1])
    qr.L75 = int(qResult[int([i for i,x in enumerate(qResult) if x.find("L75\t") > -1][-1])].split("\t")[1])
    qr.LG75 = int(qResult[int([i for i,x in enumerate(qResult) if x.find("LG75\t") > -1][-1])].split("\t")[1])
    qr.totalLength = int(qResult[int([i for i,x in enumerate(qResult) if x.find("Total length\t") > -1][-1])].split("\t")[1])
    qr.referenceLength = int(qResult[int([i for i,x in enumerate(qResult) if x.find("Reference length\t") > -1][-1])].split("\t")[1])
    qr.GC = float(qResult[int([i for i,x in enumerate(qResult) if x.find("GC (%)\t") > -1][-1])].split("\t")[1])
    qr.referenceGC = float(qResult[int([i for i,x in enumerate(qResult) if x.find("Reference GC (%)\t") > -1][-1])].split("\t")[1])
    qr.genomeFraction = float(qResult[int([i for i,x in enumerate(qResult) if x.find("Genome fraction (%)\t") > -1][-1])].split("\t")[1])
    qr.duplicationRatio = float(qResult[int([i for i,x in enumerate(qResult) if x.find("Duplication ratio\t") > -1][-1])].split("\t")[1])
    qr.data = qResult

    return qr

