process WSLH_SUMMARY {
    label 'process_low'

    container "quay.io/wslh-bioinformatics/pandas@sha256:9ba0a1f5518652ae26501ea464f466dcbb69e43d85250241b308b96406cac458"

    input:
    path qc_stats
    val runname
    path fks1_combined
    path clade_designation

    output:
    path("*_")

    when:
    task.ext.when == null || task.ext.when

    script:
    """
    python mycosnp_results_summary.py -qc ${qc_stats} -r ${runname} -f ${fks1_combined} -c ${clade_designation}
    """
}