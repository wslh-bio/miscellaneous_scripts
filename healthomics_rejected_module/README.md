# How to incorporate this module into a pipeline.
- Copy the module into the `{WORKFLOW}/modules/local/` directory.
- Add `include { REJECTED_SAMPLES  } from '../modules/local/rejected_samples'` in the `workflows/{WORKFLOW}.nf` file.
- After the standard `INPUT_CHECK` that nf-core includes in the majority of their pipelines, add:
```
workflow WORKFLOW_EXAMPLE {

    // Standard input check from all nf-core pipelines
    INPUT_CHECK (
        ch_input
    )

    // Intake channel should be set up like: [ val(meta), [ reads ] ]
    INPUT_CHECK.out.reads
        .branch{ meta, file -> 
            single_end: meta.single_end
            paired_end: !meta.single_end
            }
        .set{ ch_filtered }

    ch_filtered.paired_end
        .map{ meta, file ->
            [meta, file, file[0].countFastq(), file[1].countFastq()]}
        .branch{ meta, file, count1, count2 ->
            pass: count1 > 0 && count2 > 0
            fail: count1 == 0 || count2 == 0 || count1 == 0 && count2 == 0
        }
        .set{ ch_paired_end }

    ch_paired_end.pass
        .map { meta, file, count1, count2 -> 
            [meta, file]
            }
        .set{ {CHANNEL_NAME} }

    ch_paired_end.fail
        .map { meta, file, count1, count2 ->
            [meta.id]
            }
        .set{ ch_paired_end_fail }

    ch_paired_end_fail
        .flatten()
        .set{ ch_failed }

    ch_failed
        .ifEmpty('NO_EMPTY_SAMPLES') 
        .set{ ch_rejected_file }

    REJECTED_SAMPLES (
        ch_rejected_file,
        "WORKFLOW_NAME"
    )

    ch_all_reads = ch_all_reads.mix(ch_filtered)
    ch_versions = ch_versions.mix(INPUT_CHECK.out.versions)
}
```
**If there is no input check in the pipeline, use the map operator to manipulate the input channel to have this format: `[ val(meta), [ reads ] ]`**

# Output
The output will only include the empty sample's `meta.id`, not the the file's name. 

If the samplesheet looks like:
```
sample,fastq_1,fastq_2
empty_sample_1,samplesheets/empty_sample_1_R1_001.fastq.gz,samplesheets/empty_sample_1_R2_001.fastq.gz
empty_sample_2,samplesheets/empty_sample_2_R1_001.fastq.gz,samplesheets/empty_sample_2_R2_001.fastq.gz

```
The `meta.id` will be what is displayed in the sample column. The output of the module will result in the `rejected/{WORKFLOW}_empty_samples.csv`
```
empty_sample_1
empty_sample_2
```