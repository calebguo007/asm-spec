import json, glob, os, sys
latest = max(glob.glob('benchmark-results/benchmark-*.json'), key=os.path.getctime)
with open(latest, encoding='utf-8') as f:
    d = json.load(f)
t = d['tasks'][0]
print('--- Task #1 sample ---')
print('category:', t['category'], '| taxonomy:', t['taxonomy'])
print('pickedService:', t.get('pickedService'))
print('winnerOnchainAddress:', t.get('winnerOnchainAddress'))
print('reasoning:', t.get('reasoning'))
print('candidates:')
for c in t.get('candidates', []):
    mark = 'W' if c['picked'] else ' '
    name = c['display_name']
    price = c['price_usd']
    score = c['score']
    rank = c['rank']
    print(f'  {mark} #{rank} {name:30s} ${price:.6f}  score={score:.3f}')
print()
print('--- arcResults.fundsFlow ---')
for e in d['arcResults']['fundsFlow']:
    name = e.get('displayName') or '-'
    addr = e['address'][:14]
    cnt = e['txCount']
    total = e['totalValueUsd']
    print(f'  {name:30s}  {addr}  {cnt:2d}x  ${total:.4f}')
print()
print('uniqueRecipientCount:', d['arcResults']['uniqueRecipientCount'])
print('totalValueTransferredUsd:', d['arcResults']['totalValueTransferredUsd'])
