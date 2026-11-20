"""Read-only ERC-20 balance probe on Ethereum: where does a token's supply sit?

Public RPC reads only (totalSupply, balanceOf, owner). No keys, no orders, no state.
Usage: python balance_probe.py 0xTOKEN 0xHOLDER [0xHOLDER ...]
"""
import re
import sys

import onchain

DEAD = '0x000000000000000000000000000000000000dEaD'
ZERO = '0x' + '0' * 40


def main(argv):
    if len(argv) < 2 or not all(re.fullmatch(r'0x[0-9a-fA-F]{40}', a) for a in argv[1:]):
        print('usage: balance_probe.py 0xTOKEN [0xHOLDER ...]')
        return 2
    token, holders = argv[1], list(argv[2:]) + [DEAD, ZERO]
    rpc = onchain.Rpc('eth')
    rpc.snapshot()
    supply = onchain.uint(rpc.read(token, '18160ddd'))
    print('BAL block', int(rpc.block['number'], 16), 'totalSupply', supply / 1e18)
    for holder in holders:
        raw = rpc.balance(token, holder)
        print('BAL', holder, raw / 1e18, f'{raw / supply * 100:.4f}%' if supply else 'n/a')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
