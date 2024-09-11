//
// Check valid samplesheet and create a reads channel
//

include { FILE_SIZE_MODULE } from '../../modules/local/file_size_module'

workflow FILE_SIZE {
    take:
    samplesheet // file: /path/to/samplesheet.csv

    main:
    FILE_SIZE_MODULE ( samplesheet )
        .csv
        .splitCsv ( header:true, sep:',' )
        .map { create_fasta_channel(it) }
        .set { reads }

    emit:
    reads
    csv = FILE_SIZE_MODULE.out.csv
}

// Function to get list of [ meta, [ fasta ] ]
def create_fasta_channel(LinkedHashMap row) {
    // create meta map
    def meta = [:]
        meta.id         = row.sample

    def fasta_meta = []

    if (!file(row.fasta).exists()) {
        exit 1, "ERROR: Please check input samplesheet -> Fasta file does not exist!\n{row.fasta}"
    } else {
        fasta_meta = [ meta, [ file(row.fasta) ] ]
    }

    return fasta_meta
}