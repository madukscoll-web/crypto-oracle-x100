"""Conditional per-address concentration bounds, never beneficial-owner proof."""
from decimal import Decimal
from onchain import address
from primary_supply import integer


def estimate(rows,circulating_base_units,excluded_addresses):
    if not isinstance(rows,list)or len(rows)!=10:raise ValueError('Exactly ten ranked observations required')
    denominator=integer(circulating_base_units)
    if denominator<=0:raise ValueError('Positive denominator required')
    excluded={address(x)for x in excluded_addresses}
    seen=set();values=[];remaining=[]
    for row in rows:
        holder=address(row['address']);balance=integer(row['pinned_balance_base_units'])
        if holder in seen:raise ValueError('Duplicate holder')
        seen.add(holder);values.append(balance)
        if holder not in excluded:remaining.append(balance)
    if any(a<b for a,b in zip(values,values[1:])):raise ValueError('Ranking changed at pinned block; no bound admitted')
    known=sum(remaining)
    if known>denominator:raise ValueError('Exclusion definition conflicts with circulating denominator')
    # If these are the true top ten, any omitted address has at most the cutoff.
    # Replace each excluded address with an unseen address AT THE CUTOFF, not zero.
    upper=min(denominator,known+(10-len(remaining))*values[-1])
    return dict(status='CONDITIONAL_PROVIDER_RANKING_BOUND',
                known_nonexcluded_share=str(Decimal(known)/denominator),
                per_address_top10_upper_bound=str(Decimal(upper)/denominator),
                excluded_from_initial_list=10-len(remaining),
                ranking_independently_verified=False,beneficial_ownership_verified=False,buy_authorized=False,
                assumptions=['Provider list is the complete global top ten at this pinned block',
                             'Issuer circulating-wallet exclusions correctly define the denominator',
                             'No inference about related-wallet/common beneficial ownership'],
                meaning='Conditional per-address bound; not an exact adjusted top ten, identity audit or token approval')
