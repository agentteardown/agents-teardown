#!/bin/bash
# Основной замер EP03: продолжает с заданной точки. Аргументы: STAMP START_PASS START_H START_T
export PATH=~/.local/bin:~/.nvm/versions/node/v24.18.1/bin:$PATH
cd ~/llm-bench; M=qwen3.5:9b-ctx32k; S=$1; sp=$2; sh=$3; st=$4; go=0
for i in 1 2 3; do for h in dsh cc; do for t in t1 t2 t3 t4 t5 t6 t7; do
  [ $go = 0 ] && [ "$i/$h/$t" = "$sp/$sh/$st" ] && go=1; [ $go = 0 ] && continue
  echo "$(date +%s) START $i $h $t"
  if [ $h = dsh ]; then python3 repo-tasks/run_dsh.py $M $t; else python3 repo-tasks/run_cc_repo.py local:$M $t; fi
  echo "$(date +%s) END $i $h $t rc=$?"
done; done; done; echo "ОСНОВНОЙ ЗАМЕР ГОТОВ"
