**Purpose**

This subworkflow has been created to remove samples from the samplesheet that do not have any reads in them. This subworkflow can be incorporated into an existing pipeline, but the script can be run without pipeline incorportation, if preferred. 

**How to incorporate the subworkflow into an existing pipeline**

To use this subworkflow: 
- Add the file_size_module.nf to ```modules/local```
- Add the file_size_check.py to ```bin/```
- Add the file_size.nf to ```subworkflows/local```
- In ```workflows/<pipeline>```, import subworkflow with ```include { FILE_SIZE } from '../subworkflows/local/file_size'```
- In ```subworkflows/local/input_check.nf``` add ```csv = SAMPLESHEET_CHECK.out.csv``` to the ```emit:``` section of the workflow.
- Run the subworkflow on the INPUT_CHECK csv output using ```FILE_SIZE ( INPUT_CHECK.out.csv )```
- To use the output of the cleaned samplesheet, replace ```INPUT_CHECK.out.reads``` with ```FILE_SIZE.out.reads``` where present in the existing pipeline.

**Example Usage**
```
//
// <PIPELINE WORKFLOW SCRIPT> 
//

include { FILE_SIZE } from '../subworkflows/local/file_size'

    //
    // SUBWORKFLOW: Read in samplesheet, validate and stage input files
    //
    INPUT_CHECK (
        ch_input
    )
    .reads
    .set { ch_input_reads }

    //
    // SUBWORKFLOW: FILE SIZE, Check if there are any empty files in the samplesheet
    //
    FILE_SIZE ( INPUT_CHECK.out.csv )

    // Adding version information
    ch_versions = ch_versions.mix(INPUT_CHECK.out.versions)

    //
    // QC check for runs if skip quast
    //
    if (!params.skip_quast) {
        QUAST ( FILE_SIZE.out.reads )
        QUAST_SUMMARY (
            QUAST.out.transposed_report.collect()
            )
        ch_versions = ch_versions.mix(QUAST.out.versions)
    }

//
// INPUT_CHECK.nf 
//

```
    emit:
    reads                                     // channel: [ val(meta), [ reads ] ]
    csv = SAMPLESHEET_CHECK.out.csv
    versions = SAMPLESHEET_CHECK.out.versions // channel: [ versions.yml ]
```

**How to use the python script alone**

To use the python script without incorporating the subworkflow in a pipeline, use ```python3 file_size_check.py samplesheet.csv```