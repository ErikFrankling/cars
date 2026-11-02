#!/usr/bin/env bash
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
L=research/truth/learned
S=research/truth/scripts/learned_drivers.py
python3 -I $S es-ring --tag es_mix_s0 --seed 0 --gens 200 --reward full_tg --humans mix --lmin 220 --lmax 420 > $L/log_es_mix_s0.txt 2>&1; echo m0 $?
python3 -I $S es-ring --tag es_mix_s1 --seed 1 --gens 200 --reward full_tg --humans mix --lmin 220 --lmax 420 > $L/log_es_mix_s1.txt 2>&1; echo m1 $?
python3 -I $S es-ring --tag es_mix_s2 --seed 2 --gens 200 --reward full_tg --humans mix --lmin 220 --lmax 420 > $L/log_es_mix_s2.txt 2>&1; echo m2 $?
python3 -I $S h05 $L/es_mix_s0.npz $L/es_mix_s1.npz $L/es_mix_s2.npz $L/es_tg_s0.npz $L/es_tg_s1.npz $L/es_tgrange_s0.npz $L/ppo_tg_s0.npz $L/dagger_pi_s0.npz --out eval-h05 > $L/log_eval-h05.txt 2>&1; echo h $?
python3 -I $S eval $L/es_mix_s0.npz $L/es_mix_s1.npz $L/es_mix_s2.npz --out eval-mix > $L/log_eval-mix.txt 2>&1; echo e $?
python3 -I $S brake $L/es_mix_s0.npz $L/es_mix_s1.npz $L/es_tg_s0.npz $L/es_tg_s1.npz $L/es_tgrange_s0.npz $L/ppo_tg_s0.npz $L/dagger_pi_s0.npz $L/es_ema_s0.npz $L/ppo_s0.npz --out eval-brake > $L/log_eval-brake.txt 2>&1; echo b $?
echo total
