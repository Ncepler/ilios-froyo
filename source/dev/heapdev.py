"""Fill one or more bowls and merge them into a heaps JSON the lab / page can load:  python3 source/dev/heapdev.py out.json key,key"""
import json, sys, os, time
here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(here, '..', 'toppings')); sys.path.insert(0, os.path.join(here, '..'))
import build_toppings as bt, heaps
reg = bt.registry()
out = json.load(open(sys.argv[1])) if os.path.exists(sys.argv[1]) else {}      # (merges into an existing file)
for k in sys.argv[2].split(','):
    t = time.time()
    pcs, spec = bt.bowl_pieces(k); out[k] = heaps.make_heap(k, pcs, spec)
    print(k, f'{time.time() - t:.1f}s', len(out[k]['instances']), flush=True)
json.dump(out, open(sys.argv[1], 'w'), separators=(',', ':'))
