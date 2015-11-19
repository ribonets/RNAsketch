Rscript ../plot.R -f exit_duration_global.out -x "Exit Value [count]" -t "Exit Value with Global Sampling"
Rscript ../plot.R -f exit_duration_local.out -x "Exit Value [count]" -t "Exit Value with Local Sampling"
Rscript ../plot.R -f jump_duration_global.out -x "Jump Value [count]" -t "Jump Value with Global Sampling"
Rscript ../plot.R -f jump_duration_local.out -x "Jump Value [count]" -t "Jump Value with Local Sampling"
Rscript ../plot.R -f random_optimization_global.out -x "Sampling Duration [count]" -t "Global Sampling Duration"
Rscript ../plot.R -f random_optimization_local.out -x "Sampling Duration [count]" -t "Local Sampling Duration"
Rscript ../plot.R -f random_optimization_sample.out -x "Sampling Duration [count]" -t "Sampling Duration"