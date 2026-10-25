"""Canonical on-chain token keys. Symbols and native/wrapped aliases never merge."""
import re

CHAINS={'eth':'eip155:1','base':'eip155:8453','bsc':'eip155:56',
        'solana':'solana:5eykt4UsFv8P8NJdTREpY1vzqKqZKvdp'}
GATE_CHAINS={'ETH':'eth','BASEEVM':'base','BSC':'bsc','SOL':'solana'}
DEX_CHAINS={'eth':'ethereum','base':'base','bsc':'bsc','solana':'solana'}
ALPHABET='123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'


def canonical(network,value):
    if network not in CHAINS or not isinstance(value,str):raise ValueError('Unsupported chain/contract')
    if network!='solana':
        if not re.fullmatch('0x[0-9a-fA-F]{40}',value) or int(value[2:],16)==0:raise ValueError('Exact nonzero EVM token contract required')
        return value.lower()
    if not 32<=len(value)<=44 or any(c not in ALPHABET for c in value):raise ValueError('Invalid Solana mint encoding')
    number=0
    for char in value:number=number*58+ALPHABET.index(char)
    decoded=b'\0'*(len(value)-len(value.lstrip('1')))+(number.to_bytes((number.bit_length()+7)//8,'big') if number else b'')
    if len(decoded)!=32:raise ValueError('Solana address must decode to 32 bytes')
    return value  # case-sensitive; address shape is not a mint-account audit


def key(network,value):return CHAINS[network]+':'+canonical(network,value)


def pool_address(network,value):
    if network=='solana':return canonical(network,value)
    if network not in CHAINS or not isinstance(value,str) or not re.fullmatch(r'0x(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})',value):
        raise ValueError('Unsupported pool address/identifier')
    return value.lower()
