process FILE_SIZE_MODULE {

  container "quay.io/wslh-bioinformatics/spriggan-pandas:1.3.2"

  label 'process_single'

  input:
  path samplesheet

  output:
  path '*.csv', emit: csv

  when:
  task.ext.when == null || task.ext.when

  script: //This script is bundled with the python script within bin.
  """
  file_size_check.py $samplesheet
  """

 }