N=research/truth/fig/09-nets/j2.net.xml; T=$(seq -s, 0 1500)
export CARS_ADAPTER=llvmpipe LP_NUM_THREADS=4
for D in 3000 5200; do
  /usr/bin/env time -f "%e s" timeout 270 ./target/release/cars av --net $N --routes /tmp/brake/j2_$D.rou.xml --end 280 --cj B1 --trace 60,280,$T --json /tmp/brake/j2_$D.json 2> /tmp/brake/j2_$D.log
  wc -l /tmp/brake/j2_$D.log; grep -v "^tr " /tmp/brake/j2_$D.log | tail -2
done
